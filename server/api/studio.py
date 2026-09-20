"""NEXT PHASE backend vertical slice: sources and editable graph endpoints."""

from __future__ import annotations

import json
import hashlib
import copy
import base64
from pathlib import PurePath
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from core.assets.library import SourceLibrary
from core.assets.profile_catalog import catalog, find_profile, read_profile
from core.color.cube import apply_cube_to_image, parse_cube, serialize_leica_cube, parse_hald
from core.color.graph import graph_status, validate_color_graph
from core.color.graph_compiler import compile_graph_cube
from core.film.icons import generic_film_icon
from core.film.samples import get_sample
from core.leica.authoritative import read_look_asset
from core.leica.compiler import compile_look_payload
from core.leica.package import build_look_package
from server.auth import require_user

router = APIRouter(prefix="/studio", tags=["studio"], dependencies=[Depends(require_user)])
library = SourceLibrary()
MAX_SOURCE_BYTES = 50 * 1024 * 1024
MAX_PREVIEW_BYTES = 20 * 1024 * 1024


def _base_value(value: Any) -> int | Any:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"standard", "neutral", "color", "0"}:
            return 0
        if normalized in {"monochrome", "mono", "black and white", "1"}:
            return 1
    return value


def _ui_strength(value: Any) -> float:
    """Frontend layers use percentages; canonical graph strengths use 0..2."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"Invalid layer strength: {value!r}")
    if not 0 <= number <= 200:
        raise HTTPException(status_code=422, detail="Layer strength must be between 0 and 200 percent")
    return number / 100.0


def _manual_node(node_id: str, node_type: str, value: float) -> dict:
    return {"id": node_id, "type": node_type, "enabled": True, "strength": 1.0,
            "params": {"value": float(value) / 100.0}}


def _normalize_ui_graph(value: dict) -> dict:
    """Copy UI state into the canonical graph without changing the submitted dict."""
    if "nodes" in value:
        graph = copy.deepcopy(value)
        graph["base"] = _base_value(graph.get("base", 0))
        return graph
    if "layers" not in value:
        return copy.deepcopy(value)

    graph = {key: copy.deepcopy(item) for key, item in value.items() if key not in {"layers", "controls"}}
    graph["base"] = _base_value(graph.get("base", 0))
    nodes: list[dict] = [{"id": "input", "type": "input", "enabled": True, "strength": 1.0}]
    type_map = {
        "normalization": "camera_normalization",
        "input_normalization": "camera_normalization",
        "tone": "tone",
        "tone_curve": "tone_curve",
        "lut": "lut",
        "cube": "cube_lut",
        "output": "output",
        "component": "source_component",
        "settings": "source_component",
        "table": "source_component",
    }
    for position, layer in enumerate(value.get("layers") or []):
        if not isinstance(layer, dict):
            raise HTTPException(status_code=422, detail=f"Layer {position} must be an object")
        item = copy.deepcopy(layer)
        raw_type = str(item.get("type") or "source_component").strip().lower()
        name = str(item.get("name") or "").lower()
        if raw_type == "grading":
            item["type"] = ("shadow_grade" if "shadow" in name else
                            "highlight_grade" if "highlight" in name else "midtone_grade")
        else:
            item["type"] = type_map.get(raw_type, raw_type)
        item["id"] = str(item.get("id") or f"layer-{position}")
        if item["id"] in {"input", "output"}:
            item["id"] = f"layer-{item['id']}"
        item["enabled"] = bool(item.get("enabled", True))
        item["strength"] = _ui_strength(item.get("strength", 100))
        item["solo"] = bool(value.get("solo") == layer.get("id"))
        # The UI can only resolve a component when both immutable identifiers
        # are present.  A filename is retained for diagnostics, never guessed.
        if item.get("source") and not (item.get("source_id") and item.get("component_id")):
            item["unresolved_source"] = item["source"]
        nodes.append(item)

    controls = value.get("controls") or {}
    if not isinstance(controls, dict):
        raise HTTPException(status_code=422, detail="Graph controls must be an object")
    basic = ("exposure", "contrast", "highlights", "shadows", "whites", "blacks",
             "temperature", "tint", "saturation", "vibrance")
    for control in basic:
        raw = controls.get(control, 0)
        try:
            number = float(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"Invalid control value: {control}")
        if not -100 <= number <= 100:
            raise HTTPException(status_code=422, detail=f"Control {control} must be between -100 and 100")
        nodes.append(_manual_node(f"control-{control}", control, number))

    grade_specs = (
        ("shadow_grade", "shadowHue", "shadowSat", "shadowLum"),
        ("midtone_grade", "midHue", "midSat", "midLum"),
        ("highlight_grade", "highlightHue", "highlightSat", "highlightLum"),
    )
    for node_type, hue_key, sat_key, lum_key in grade_specs:
        hue = float(controls.get(hue_key, 0))
        sat = float(controls.get(sat_key, 0))
        lum = float(controls.get(lum_key, 0))
        if not 0 <= hue <= 360 or not -100 <= sat <= 100 or not -100 <= lum <= 100:
            raise HTTPException(status_code=422, detail=f"Invalid {node_type} controls")
        if hue or sat or lum:
            nodes.append({"id": f"control-{node_type}", "type": node_type, "enabled": True,
                          "strength": 1.0, "params": {"hue": hue, "amount": sat / 100.0,
                                                       "luminance": lum / 100.0}})

    film_controls = (("toe", "film_toe"), ("shoulder", "film_shoulder"),
                     ("blackLift", "black_lift"), ("rolloff", "highlight_rolloff"))
    for control, node_type in film_controls:
        raw = float(controls.get(control, 0))
        if not -100 <= raw <= 100:
            raise HTTPException(status_code=422, detail=f"Control {control} must be between -100 and 100")
        if raw:
            nodes.append(_manual_node(f"control-{node_type}", node_type, raw))
    for control, node_type in (("midContrast", "contrast"), ("density", "saturation")):
        raw = float(controls.get(control, 0))
        if not -100 <= raw <= 100:
            raise HTTPException(status_code=422, detail=f"Control {control} must be between -100 and 100")
        if raw:
            nodes.append(_manual_node(f"control-{control}", node_type, raw))
    if False: # balance is applied to tonal grade masks below
        nodes.append({"id": "control-balance", "type": "midtone_grade", "enabled": True,
                      "strength": 1.0, "params": {"balance": float(controls["balance"]) / 100.0}})
    for control in ("monoMix", "yellowFilter", "orangeFilter", "redFilter", "greenFilter"):
        raw = float(controls.get(control, 0))
        if raw:
            nodes.append({"id": f"control-{control}", "type": "monochrome_filter",
                          "enabled": True, "strength": 1.0,
                          "params": {"value": raw / 100.0, "filter": control}})
    if not any(node.get("type") == "output" for node in nodes):
        nodes.append({"id": "output", "type": "output", "enabled": True, "strength": 1.0})
    for n in nodes:
        if n.get("type") in {"shadow_grade", "midtone_grade", "highlight_grade"}:
            n.setdefault("params", {})["balance"] = float(controls.get("balance", 0))/100
    # Mixtures evaluate each source against the same input. A serial stack remains available.
    if value.get("mix_mode") == "mixture":
        ingredients = [n for n in nodes if n.get("source_id") and n.get("enabled",True)]
        if ingredients:
            branch = {"id":"source-mixture", "type":"blend", "enabled":True,
                      "solo": any(n.get("solo") for n in ingredients), "branches":[]}
            solos = [n for n in ingredients if n.get("solo")]
            for n in solos or ingredients:
                weight=n["strength"]
                child=copy.deepcopy(n); child["strength"]=1; child["solo"]=False
                branch["branches"].append({"weight":weight,"nodes":[child]})
            first = nodes.index(ingredients[0])
            nodes = [n for n in nodes if n not in ingredients]
            nodes.insert(min(first,len(nodes)),branch)
    graph["nodes"] = nodes
    return graph


def _graph(value: Any) -> dict:
    if isinstance(value, dict):
        graph = value
    elif isinstance(value, str):
        try:
            graph = json.loads(value)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=f"Graph JSON is invalid: {exc}") from exc
    else:
        raise HTTPException(status_code=422, detail="Graph must be a JSON object")
    if "nodes" not in graph and isinstance(graph.get("graph"), dict):
        nested = dict(graph["graph"])
        nested.update({key: value for key, value in graph.items() if key != "graph"})
        graph = nested
    graph = _normalize_ui_graph(graph)
    try:
        validate_color_graph(graph)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return graph


async def _request_graph(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        value = form.get("graph") or form.get("graph_json")
        if isinstance(value, dict):
            result = value
        else:
            try:
                result = json.loads(value)
            except (TypeError, json.JSONDecodeError) as exc:
                raise HTTPException(status_code=422, detail="Graph JSON is invalid") from exc
    else:
        try:
            result = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Request body must contain graph JSON") from exc
    if not isinstance(result, dict):
        raise HTTPException(status_code=422, detail="Graph must be a JSON object")
    if "nodes" not in result and isinstance(result.get("graph"), dict):
        nested = dict(result["graph"])
        nested.update({key: value for key, value in result.items() if key != "graph"})
        result = nested
    return _normalize_ui_graph(result)


async def _limited(upload: UploadFile, limit: int) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"Upload exceeds {limit // (1024 * 1024)} MB")
    return data


@router.get("/sources")
def sources(search: Optional[str] = None, type: Optional[str] = None, asset_type: Optional[str] = None):
    requested_type = (asset_type or type or "").strip()
    aliases = {
        "leica look": "leica_payload", "leica": "leica_payload",
        "image reference": "reference_image", "raw image": "raw_image",
    }
    requested_type = aliases.get(requested_type.lower(), requested_type)
    items = library.list(search=search, asset_type=requested_type or None)
    return {"count": len(items), "sources": items}


@router.post("/sources/bulk", status_code=201)
async def upload_sources_bulk(
    files: list[UploadFile] = File(...),
    provenance: str = Form(""),
    interpretation: str = Form("auto"),
):
    if not files:
        raise HTTPException(status_code=422, detail="At least one source file is required")
    results = []
    for upload in files:
        content = await _limited(upload, MAX_SOURCE_BYTES)
        if not content:
            raise HTTPException(status_code=422, detail=f"{upload.filename or 'source'} is empty")
        try:
            filename=upload.filename or "unnamed"
            if interpretation == "hald":
                path=PurePath(filename); filename=path.stem+".hald"+path.suffix
            result = library.add(filename, content, upload.content_type, provenance)
        except (ValueError, UnicodeError) as exc:
            raise HTTPException(status_code=422, detail=f"{upload.filename}: {exc}") from exc
        results.append(result)
    return {
        "count": len(results),
        "created": sum(not result["duplicate"] for result in results),
        "duplicates": sum(result["duplicate"] for result in results),
        "sources": results,
    }


@router.post("/sources/from-look/{look_id}", status_code=201)
def source_from_look(look_id: int):
    """Catalog a verified built-in Look under its public, camera-neutral name."""
    try:
        sample = get_sample(look_id)
        content = read_look_asset(sample["source_id"], "cube")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    filename = f'{sample["key"]}.CUBE'
    result = library.add(
        filename,
        content,
        "text/plain",
        {
            "origin": "verified built-in Look",
            "public_name": sample["name"],
            "public_id": sample["id"],
            "immutable_fixture_id": sample["source_id"],
        },
    )
    result["display_name"] = sample["name"]
    return result


@router.get("/profile-catalog")
def profile_catalog(search: Optional[str] = None, type: Optional[str] = None):
    needle = (search or "").strip().lower()
    requested_type = (type or "").strip().lower()
    items = [
        dict(item) for item in catalog()
        if (not needle or needle in item["display_name"].lower())
        and (not requested_type or item["asset_type"] == requested_type)
    ]
    return {"count": len(items), "profiles": items}


@router.post("/profile-catalog/{catalog_id}/import", status_code=201)
def import_profile(catalog_id: str):
    profile = find_profile(catalog_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found in immutable catalog")
    content = read_profile(profile)
    extension = PurePath(profile["member"]).suffix.upper()
    filename = f'{profile["display_name"]}{extension}'
    result = library.add(
        filename,
        content,
        "application/octet-stream" if extension == ".DCP" else "text/plain",
        {"origin": "uploaded immutable profile catalog", "archive_member": profile["member"]},
    )
    result["display_name"] = profile["display_name"]
    return result


@router.get("/sources/{source_id}")
def source_detail(source_id: str):
    result = library.get(source_id)
    if not result:
        raise HTTPException(status_code=404, detail="Source not found")
    return result


@router.get("/sources/{source_id}/download")
def source_download(source_id: str):
    result = library.get(source_id, include_content=True)
    if not result:
        raise HTTPException(status_code=404, detail="Source not found")
    return Response(
        result["content"], media_type=result["media_type"],
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"',
                 "X-Source-SHA256": result["sha256"], "Cache-Control": "no-store"},
    )


def _compiled(graph: dict) -> tuple[bytes, dict]:
    graph = _hydrate_graph(graph)
    status = graph_status(graph)
    if status.get("errors"):
        raise HTTPException(status_code=422, detail={
            "message": "Graph contains unresolved or incomplete components",
            "errors": status["errors"],
        })
    try:
        return compile_graph_cube(graph, size=17)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _hydrate_graph(graph: dict) -> dict:
    """Resolve a library component reference without changing the master graph."""
    resolved = copy.deepcopy(graph)
    def hydrate(nodes):
        for node in nodes:
            for branch in node.get("branches", []): hydrate(branch.get("nodes", []))
            source_id, component_id = node.get("source_id"), node.get("component_id")
            if not source_id or not component_id or not node.get("enabled", True): continue
            source = library.get(str(source_id), include_content=True)
            if not source: raise HTTPException(status_code=422, detail=f"Source not found: {source_id}")
            component = next((c for c in source["components"] if c.get("id")==component_id),None)
            if not component: raise HTTPException(status_code=422, detail=f"Component not found: {component_id}; reselect the source")
            kind=component["type"]
            node["source_sha256"] = source["sha256"]
            node["type"] = kind
            if kind=="cube_lut":
                embedded=(component.get("metadata") or {}).get("embedded_base64")
                if source["asset_type"]=="hald":
                    hald=parse_hald(source["content"])
                    node["_parsed_cube"] = hald
                    node["cube"] = "HALD_INTERNAL"
                else: node["cube"]=base64.b64decode(embedded) if embedded else source["content"]
                input_space=node.get("input_space", "srgb")
                if "flog" in (source["filename"]+str(source.get("provenance",""))+str(source.get("metadata",{}).get("title",""))).lower() or input_space not in {"srgb","display_rgb"}:
                    raise HTTPException(status_code=422,detail="This source needs its input color-space conversion. A log LUT cannot be applied directly to a rendered photo.")
            elif kind=="matrix":
                values=component["values"]
                if isinstance(values,list) and len(values)==9: values=[values[i:i+3] for i in range(0,9,3)]
                node.update(matrix=values,camera_dependent=source["asset_type"]=="dcp")
            elif kind=="tone_curve": node["points"]=component["values"]
            elif kind=="dcp_creative":
                node["tags"]=component["tags"]
                baseline_id=node.get("baseline_source_id")
                if baseline_id:
                    baseline=library.get(str(baseline_id),include_content=True)
                    if not baseline or baseline["asset_type"]!="dcp": raise HTTPException(status_code=422,detail="DCP baseline not found")
                    node.update(baseline_tags=baseline["metadata"]["tags"],mode="relative_display")
            elif kind=="preset_creative": node["settings"]=component["settings"]
            else: node.update(component=component,type="source_component")
    hydrate(resolved.get("nodes", []))
    return resolved


@router.post("/graph/validate")
@router.post("/graph/status")
async def validate_graph(request: Request):
    graph = await _request_graph(request)
    try:
        _cube, report = _compiled(graph)
        return report
    except HTTPException as exc:
        return {"valid":False,"ready":False,"errors":[exc.detail]}


@router.post("/graph/cube")
async def graph_cube(request: Request):
    graph = await _request_graph(request)
    cube, report = _compiled(graph)
    return Response(
        cube, media_type="text/plain",
        headers={
            "X-Graph-Valid": "true",
            "X-Graph-Status": "ready" if report.get("ready") else "non-blendable-components",
            "X-CUBE-SHA256": hashlib.sha256(cube).hexdigest(),
            "Content-Disposition": 'attachment; filename="compiled-graph.CUBE"',
        },
    )


@router.post("/dcp/cube")
async def dcp_cube(
    dcp: UploadFile = File(...),
    look_id: int = Form(1200),
    name: str = Form(""),
    base: int = Form(0),
    strength: float = Form(1.0),
    tone_curve: bool = Form(False),
):
    """Convert a DCP creative profile directly into a Leica-headed 17³ CUBE."""
    from core.color.dcp_export import dcp_to_leica_cube

    data = await _limited(dcp, MAX_SOURCE_BYTES)
    filename = dcp.filename or "profile.dcp"
    if not filename.lower().endswith(".dcp"):
        raise HTTPException(status_code=422, detail="Upload a .dcp file")
    try:
        cube = dcp_to_leica_cube(
            data,
            look_id=look_id,
            name=name.strip() or None,
            base=0 if base not in (0, 1) else base,
            filename=filename,
            strength=strength,
            include_tone_curve=tone_curve,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    title = (name.strip() or PurePath(filename).stem).replace('"', "")
    return Response(
        cube,
        media_type="text/plain",
        headers={
            "X-CUBE-SHA256": hashlib.sha256(cube).hexdigest(),
            "X-Builder-Method": "dcp-creative-v1",
            "Content-Disposition": f'attachment; filename="{title}.CUBE"',
        },
    )


@router.post("/graph/preview")
async def graph_preview(request: Request):
    if "multipart/form-data" not in request.headers.get("content-type", ""):
        raise HTTPException(status_code=415, detail="Preview requires multipart graph and image fields")
    form = await request.form()
    graph = _graph(form.get("graph") or form.get("graph_json"))
    image = form.get("image") or form.get("photo")
    if image is None or not hasattr(image, "read"):
        raise HTTPException(status_code=422, detail="Preview requires an image field")
    image_data = await _limited(image, MAX_PREVIEW_BYTES)
    cube, report = _compiled(graph)
    try:
        rendered = apply_cube_to_image(image_data, parse_cube(cube))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not render graph preview: {exc}") from exc
    return Response(rendered, media_type="image/jpeg", headers={
        "X-Graph-Status": "ready" if report.get("ready") else "non-blendable-components",
        "Cache-Control": "no-store",
    })


async def _package_values(request: Request) -> tuple[dict, bytes | None]:
    content_type = request.headers.get("content-type", "")
    icon = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        graph = _graph(form.get("graph") or form.get("graph_json"))
        # The web client keeps export metadata in multipart fields for
        # compatibility with the original Leica package endpoint.  Merge it
        # into the copied canonical graph before compilation.
        if form.get("name"):
            graph["name"] = str(form["name"])
        if form.get("look_id"):
            graph["look_id"] = str(form["look_id"])
        if form.get("base"):
            graph["base"] = _base_value(str(form["base"]))
        if form.get("description") is not None:
            graph["description"] = str(form.get("description") or "")
        if form.get("provenance") is not None:
            graph["provenance"] = str(form.get("provenance") or "")
        icon_upload = form.get("icon")
        if icon_upload is not None and hasattr(icon_upload, "read"):
            icon = await _limited(icon_upload, MAX_PREVIEW_BYTES)
        return graph, icon
    return _graph(await request.json()), None


def _look_id(value: Any) -> int:
    if isinstance(value, str):
        text = value.strip()
        if text.upper().startswith("AUTO-"):
            text = text[5:]
        try:
            value = int(text)
        except ValueError as exc:
            raise ValueError("look_id must be an integer or AUTO-<integer>") from exc
    return int(value)


def build_graph_package_bytes(graph: dict, icon: bytes | None = None) -> bytes:
    graph = _normalize_ui_graph(graph)
    cube, _report = _compiled(graph)
    name = str(graph.get("name") or "Compiled Graph").strip()
    try:
        look_id = _look_id(graph.get("look_id", 2000))
        base = int(_base_value(graph.get("base", 0)))
        d864 = int(graph.get("d864", 2))
        if icon is None:
            icon = generic_film_icon(name)
        # Leica export remains a derived v1.2 artifact.  Monochrome conversion
        # happens only here and never mutates the graph.
        leica_cube = serialize_leica_cube(parse_cube(cube), look_id, name, base)
        payload, report = compile_look_payload(look_id, name, icon, leica_cube, d864, base)
        if not all(report["verification"].values()):
            raise RuntimeError("Leica v1.2 round-trip verification failed")
        package = build_look_package(
            name=name, look_id=look_id, base=base, icon=icon, cube=leica_cube,
            payload=payload, provenance=str(graph.get("provenance", "editable graph")),
            description=str(graph.get("description", "Compiled from editable color graph")),
        )
    except (ValueError, RuntimeError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    import io, zipfile
    frozen = _hydrate_graph(graph)
    def identities(nodes):
        result=[]
        for node in nodes:
            if node.get("source_id"): result.append({k:node.get(k) for k in ("source_id","component_id","source_sha256","name","mode","baseline_source_id")})
            for branch in node.get("branches",[]): result.extend(identities(branch.get("nodes",[])))
        return result
    with zipfile.ZipFile(io.BytesIO(package)) as original:
        files={name:original.read(name) for name in original.namelist() if name!="checksums.txt"}
    files["recipe.json"]=json.dumps(graph,indent=2).encode()
    files["source_provenance.json"]=json.dumps(identities(frozen["nodes"]),indent=2).encode()
    files["engine_report.json"]=json.dumps(_report,indent=2).encode()
    files["checksums.txt"]=("\n".join(f"{hashlib.sha256(data).hexdigest()}  {name}" for name,data in sorted(files.items()))+"\n").encode()
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
    return buffer.getvalue()


@router.post("/graph/package")
async def graph_package(request: Request):
    graph, icon = await _package_values(request)
    package = build_graph_package_bytes(graph, icon)
    return Response(package, media_type="application/zip", headers={
        "Content-Disposition": 'attachment; filename="compiled-graph-leica-package.zip"',
        "X-Round-Trip-Verified": "true",
        "X-Package-SHA256": hashlib.sha256(package).hexdigest(),
    })