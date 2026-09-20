from __future__ import annotations

import hashlib
import io
import json
import os
import re
import asyncio
import urllib.error
import urllib.request
import zipfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core.leica.authoritative import get_authoritative_look, read_look_asset
from core.color.cube import apply_cube_to_image, parse_cube, serialize_leica_cube
from core.color.film_builder import build_film_cube, infer_settings
from core.assets.inspect import inspect_source_asset
from core.film.samples import SAMPLES, get_sample
from core.film.icons import generic_film_icon
from core.leica.compiler import compile_look_payload
from core.leica.package import build_look_package, generated_injector_source, package_readme
from core.leica.parser import parse_look_payload

router = APIRouter(prefix="/leica", tags=["leica-look-lab"])
MAX_UPLOAD_BYTES = 30 * 1024 * 1024


class PackInput(BaseModel):
    look_ids: list[int] = Field(min_length=1, max_length=9)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "leica-look"


def _source_id(sample_or_fixture_id: int) -> int:
    try:
        return get_sample(sample_or_fixture_id)["source_id"]
    except KeyError:
        return sample_or_fixture_id


def _source_icon(sample_or_fixture_id: int) -> bytes:
    try:
        return generic_film_icon(get_sample(sample_or_fixture_id)["name"])
    except KeyError:
        return read_look_asset(sample_or_fixture_id, "icon")


def _request_claude(api_key: str, prompt: dict) -> dict:
    body = json.dumps({
        "model": "claude-3-5-haiku-latest",
        "max_tokens": 500,
        "system": "You are a photographic color scientist. Return only one JSON object matching the requested schema. Do not include markdown. Use restrained, plausible film-style adjustments.",
        "messages": [{"role": "user", "content": json.dumps(prompt)}],
    }).encode()
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read())
    text = payload["content"][0]["text"].strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


def _summary(parsed: dict) -> dict:
    result = {key: value for key, value in parsed.items() if key not in {"icon", "cube"}}
    for field in result["fields"]:
        if isinstance(field["value"], bytes):
            field["value"] = {
                "bytes": len(field["value"]),
                "sha256": hashlib.sha256(field["value"]).hexdigest(),
            }
    return result


async def _read_limited(upload: UploadFile) -> bytes:
    if upload.size is not None and upload.size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds 30 MB")
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds 30 MB")
    return data


@router.get("/looks/{look_id}/download")
def download_authoritative_payload(look_id: int):
    try:
        look = get_authoritative_look(look_id)
        payload, report = compile_look_payload(
            look["id"],
            look["name"],
            read_look_asset(look_id, "icon"),
            read_look_asset(look_id, "cube"),
            2,
            look["base"],
        )
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, KeyError) else 422, detail=str(exc)) from exc
    return Response(
        payload,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{_slug(look["name"])}.leica-payload.bin"',
            "X-Payload-SHA256": hashlib.sha256(payload).hexdigest(),
            "X-Compile-Verified": str(all(report["verification"].values())).lower(),
            "Cache-Control": "no-store",
        },
    )


@router.post("/compile")
async def compile_payload(
    look_id: int = Form(...),
    name: str = Form(...),
    base: int = Form(...),
    d864: int = Form(2),
    source_look_id: int | None = Form(None),
    icon: UploadFile | None = File(None),
    cube: UploadFile | None = File(None),
):
    source_id = _source_id(source_look_id or look_id)
    try:
        icon_data = await _read_limited(icon) if icon else _source_icon(source_look_id or look_id)
        source_cube = await _read_limited(cube) if cube else read_look_asset(source_id, "cube")
        cube_data = serialize_leica_cube(parse_cube(source_cube), look_id, name.strip(), base)
        payload, report = compile_look_payload(look_id, name, icon_data, cube_data, d864, base)
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        payload,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{_slug(name)}.leica-payload.bin"',
            "X-Payload-SHA256": hashlib.sha256(payload).hexdigest(),
            "X-Compile-Verified": str(all(report["verification"].values())).lower(),
            "Cache-Control": "no-store",
        },
    )


@router.post("/package")
async def compile_package(
    look_id: int = Form(...),
    name: str = Form(...),
    base: int = Form(...),
    description: str = Form(""),
    provenance: str = Form(...),
    source_look_id: int | None = Form(None),
    icon: UploadFile | None = File(None),
    cube: UploadFile | None = File(None),
):
    source_id = _source_id(source_look_id or look_id)
    try:
        icon_data = await _read_limited(icon) if icon else _source_icon(source_look_id or look_id)
        source_cube = await _read_limited(cube) if cube else read_look_asset(source_id, "cube")
        cube_data = serialize_leica_cube(parse_cube(source_cube), look_id, name.strip(), base)
        payload, report = compile_look_payload(look_id, name, icon_data, cube_data, 2, base)
        if not all(report["verification"].values()):
            raise RuntimeError("Round-trip verification did not pass")
        package = build_look_package(
            name=name.strip(),
            look_id=look_id,
            base=base,
            icon=icon_data,
            cube=cube_data,
            payload=payload,
            provenance=provenance,
            description=description,
        )
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        package,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{_slug(name)}-leica-look-package.zip"',
            "X-Package-SHA256": hashlib.sha256(package).hexdigest(),
            "X-Round-Trip-Verified": "true",
            "Cache-Control": "no-store",
        },
    )


@router.post("/smart-cube")
async def smart_cube(
    name: str = Form(...),
    look_id: int = Form(...),
    intent: str = Form(...),
    profile: UploadFile | None = File(None),
):
    if not profile:
        raise HTTPException(422, "Choose a source in Look Builder, then use the creative assistant for description-driven edits.")
    from server.api.studio import library, _compiled
    data=await _read_limited(profile)
    try:
        source=library.add(profile.filename or "source",data,profile.content_type,"Smart source import")
        preferred={"cube":"cube_lut","hald":"cube_lut","leica_payload":"cube_lut","dcp":"dcp_creative","xmp":"preset_creative","lrtemplate":"preset_creative"}.get(source["asset_type"])
        component=next((c for c in source["components"] if c["type"]==preferred),None)
        if not component: raise ValueError("This source supplies reference information, not a directly recoverable transform. Use the reference analysis in Look Builder.")
        graph={"name":name.strip(),"base":0,"nodes":[{"id":"input","type":"input"},
            {"id":"source","type":"source_component","source_id":source["id"],"component_id":component["id"]},
            {"id":"output","type":"output"}]}
        cube,_=_compiled(graph)
        cube=serialize_leica_cube(parse_cube(cube),look_id,name.strip(),0)
    except (ValueError,UnicodeError) as exc: raise HTTPException(422,str(exc)) from exc
    return Response(cube,media_type="text/plain",headers={"Content-Disposition":f'attachment; filename="{_slug(name)}.CUBE"',
        "X-Builder-Method":"source-aware-v2","X-Builder-Rationale":"Source interpreted; use editable graph assistant for intent adjustments"})


@router.post("/render-cube")
async def render_custom_cube(
    image: UploadFile = File(...),
    cube: UploadFile = File(...),
):
    image_data = await _read_limited(image)
    cube_data = await _read_limited(cube)
    try:
        rendered = apply_cube_to_image(image_data, parse_cube(cube_data))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not render custom transform: {exc}") from exc
    return Response(rendered, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.post("/inspect")
async def inspect_uploaded_payload(payload: UploadFile = File(...)):
    data = await _read_limited(payload)
    try:
        parsed = parse_look_payload(data, include_binary=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "filename": payload.filename,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "validation": "VALID",
        **_summary(parsed),
    }


@router.post("/inspect/extract-cube")
async def extract_cube(payload: UploadFile = File(...)):
    data = await _read_limited(payload)
    try:
        parsed = parse_look_payload(data, include_binary=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        parsed["cube"],
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{_slug(parsed["name"])}.CUBE"',
            "X-CUBE-SHA256": hashlib.sha256(parsed["cube"]).hexdigest(),
        },
    )


def _zip_write(archive: zipfile.ZipFile, path: str, data: bytes) -> None:
    info = zipfile.ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


@router.post("/packs")
def build_pack(pack: PackInput):
    if len(set(pack.look_ids)) != len(pack.look_ids):
        raise HTTPException(status_code=422, detail="Pack contains duplicate Look IDs")
    records = []
    artifacts = []
    try:
        for look_id in sorted(pack.look_ids):
            sample = get_sample(look_id)
            fixture = get_authoritative_look(sample["source_id"])
            look = {**fixture, **sample, "name": sample["name"]}
            cube = serialize_leica_cube(parse_cube(read_look_asset(sample["source_id"], "cube")), look_id, sample["name"], fixture["base"])
            icon = generic_film_icon(sample["name"])
            payload, report = compile_look_payload(look_id, sample["name"], icon, cube, 2, fixture["base"])
            slug = _slug(look["name"])
            records.append({
                **look,
                "payload": f"looks/{slug}.leica-payload.bin",
                "payload_sha256": hashlib.sha256(payload).hexdigest(),
                "cube_sha256": hashlib.sha256(cube).hexdigest(),
                "cube_bytes": len(cube),
                "icon_sha256": hashlib.sha256(icon).hexdigest(),
                "icon_bytes": len(icon),
                "compile_parse_verified": all(report["verification"].values()),
            })
            artifacts.append((f"looks/{slug}.leica-payload.bin", payload))
            artifacts.append((look["cube"], cube))
            artifacts.append((look["icon"], icon))
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    manifest = {
        "format": "Generic Leica film-look payload pack",
        "version": 1,
        "source": "Verified internal regression fixtures with generic public sample identities",
        "note": "Payload binaries reproduce the proven v1.2 writer record. No official SD-card import container is claimed.",
        "looks": records,
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode()
    entries = [
        ("manifest.json", manifest_bytes),
        ("looks_manifest.json", json.dumps(records, indent=2, sort_keys=True).encode()),
        ("injector.py", generated_injector_source()),
        ("README.md", package_readme("Generic Leica Film Look Pack", 0, "Mixed", "Verified regression samples", hashlib.sha256(manifest_bytes).hexdigest())),
        *artifacts,
    ]
    checksum_bytes = ("\n".join(
        f"{hashlib.sha256(data).hexdigest()}  {path}" for path, data in sorted(entries)
    ) + "\n").encode()
    entries.append(("checksums.txt", checksum_bytes))
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path, data in entries:
            _zip_write(archive, path, data)
    data = output.getvalue()
    return Response(
        data,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="generic-leica-film-look-pack.zip"',
            "X-Pack-SHA256": hashlib.sha256(data).hexdigest(),
            "X-Look-Count": str(len(records)),
            "Cache-Control": "no-store",
        },
    )