from __future__ import annotations

import hashlib
import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from core.assets.inspect import inspect_source_asset
from core.color.cube import apply_cube_to_image, parse_cube
from core.color.graph import default_color_graph
from core.fuji.recipes import load_camera_profiles, validate_recipe
from core.leica.authoritative import (
    archive_inventory,
    get_authoritative_look,
    load_authoritative_manifest,
    read_look_asset,
)
from core.leica.payload import build_authoritative_payload, inspect_payload
from server.db.database import engine
from server.services.bridge_jobs import create_job, get_job


router = APIRouter(tags=["photo-lab"])
ROOT = Path(__file__).resolve().parents[2]


class FujiRecipeInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    camera_profile_id: str
    look_id: int | None = None
    settings: dict = Field(default_factory=dict)
    provenance: str = Field(min_length=3, max_length=1000)


class BridgeJobInput(BaseModel):
    job_type: str
    bridge_id: str | None = None
    payload: dict = Field(default_factory=dict)


@router.get("/library")
def library():
    looks = load_authoritative_manifest()
    return {
        "name": "Infinite Arch Photo Lab",
        "version": "Leica v1.2",
        "look_count": len(looks),
        "looks": looks,
        "principle": "One Look family, multiple target-specific implementations.",
    }


@router.get("/inventory")
def inventory():
    items = archive_inventory()
    return {"count": len(items), "items": items}


@router.get("/looks/{look_id}")
def look_detail(look_id: int):
    try:
        look = get_authoritative_look(look_id)
        cube = parse_cube(read_look_asset(look_id, "cube"))
        payload = inspect_payload(build_authoritative_payload(look_id))
    except (KeyError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=404 if isinstance(exc, KeyError) else 500, detail=str(exc)) from exc
    return {
        **look,
        "look_family": {"slug": look["key"], "name": look["name"]},
        "implementation": {
            "target": "LEICA_Q3_FAMILY",
            "version": "1.2",
            "verification_status": "authoritative_archive",
        },
        "cube_summary": cube.summary(),
        "payload_summary": payload,
        "provenance": {
            "archive": "reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip",
            "immutable": True,
        },
        "color_graph": default_color_graph(),
    }


@router.get("/looks/{look_id}/icon")
def look_icon(look_id: int):
    try:
        data = read_look_asset(look_id, "icon")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(data, media_type="image/bmp", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.post("/looks/{look_id}/render")
async def render_look(
    look_id: int,
    image: UploadFile = File(...),
    output_format: str = Query(default="jpeg", pattern="^(jpeg|tiff)$"),
):
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image")
    data = await image.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds the 20 MB preview limit")
    try:
        rendered = apply_cube_to_image(data, parse_cube(read_look_asset(look_id, "cube")))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not render image: {exc}") from exc
    if output_format == "tiff":
        from io import BytesIO
        from PIL import Image

        buffer = BytesIO()
        Image.open(BytesIO(rendered)).save(buffer, format="TIFF", compression="tiff_lzw")
        rendered = buffer.getvalue()
    media_type = "image/tiff" if output_format == "tiff" else "image/jpeg"
    extension = "tiff" if output_format == "tiff" else "jpg"
    return Response(
        rendered,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="ia-look-{look_id}.{extension}"',
            "X-Source-SHA256": hashlib.sha256(data).hexdigest(),
            "Cache-Control": "no-store",
        },
    )


@router.get("/assets")
def list_assets():
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id,sha256,filename,media_type,asset_type,size,provenance,"
                "storage_key,imported_at,immutable FROM source_assets ORDER BY imported_at DESC"
            )
        ).mappings()
        return [dict(row) for row in rows]


@router.post("/assets", status_code=201)
async def upload_asset(
    asset: UploadFile = File(...),
    provenance: str = Query(min_length=3, max_length=1000),
):
    content = await asset.read()
    if not content or len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Source assets must be between 1 byte and 30 MB")
    try:
        inspection = inspect_source_asset(asset.filename or "unnamed", content)
    except (ValueError, ET.ParseError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    digest = hashlib.sha256(content).hexdigest()
    asset_id = str(uuid.uuid4())
    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT id FROM source_assets WHERE sha256=:sha256"), {"sha256": digest}
        ).scalar()
        if existing:
            return {"id": existing, "sha256": digest, "duplicate": True, **inspection}
        connection.execute(
            text(
                "INSERT INTO source_assets(id,sha256,filename,media_type,asset_type,size,provenance,"
                "storage_key,immutable) VALUES(:id,:sha256,:filename,:media_type,:asset_type,:size,"
                ":provenance,:storage_key,TRUE)"
            ),
            {
                "id": asset_id,
                "sha256": digest,
                "filename": asset.filename or "unnamed",
                "media_type": asset.content_type or "application/octet-stream",
                "asset_type": inspection["asset_type"],
                "size": len(content),
                "provenance": provenance,
                "storage_key": f"postgresql://source_asset_blobs/{asset_id}",
            },
        )
        connection.execute(
            text("INSERT INTO source_asset_blobs(asset_id,content) VALUES(:id,:content)"),
            {"id": asset_id, "content": content},
        )
    return {"id": asset_id, "sha256": digest, "duplicate": False, **inspection}


@router.get("/assets/{asset_id}/download")
def download_asset(asset_id: str):
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT a.filename,a.media_type,b.content FROM source_assets a "
                "JOIN source_asset_blobs b ON b.asset_id=a.id WHERE a.id=:id"
            ),
            {"id": asset_id},
        ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Source asset not found")
    return Response(
        row["content"],
        media_type=row["media_type"],
        headers={"Content-Disposition": f'attachment; filename="{row["filename"]}"', "Cache-Control": "no-store"},
    )


@router.get("/camera-profiles")
def camera_profiles():
    paths = sorted((ROOT / "camera_profiles").glob("*.json"))
    profiles = []
    for path in paths:
        item = json.loads(path.read_text())
        item["id"] = path.stem.upper()
        profiles.append(item)
    return profiles


@router.get("/fuji/recipes")
def list_fuji_recipes():
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT * FROM fuji_recipes ORDER BY created_at DESC")).mappings()
        return [dict(row) for row in rows]


@router.post("/fuji/recipes", status_code=201)
def create_fuji_recipe(recipe: FujiRecipeInput):
    try:
        validation = validate_recipe(recipe.camera_profile_id, recipe.settings)
        look_version_id = None
        if recipe.look_id is not None:
            look = get_authoritative_look(recipe.look_id)
            look_version_id = f"{look['key']}:v1.2"
        recipe_id = str(uuid.uuid4())
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO fuji_recipes(id,look_version_id,camera_profile_id,name,settings,"
                    "provenance,verification_status) VALUES(:id,:look_version_id,:camera_profile_id,"
                    ":name,CAST(:settings AS jsonb),:provenance,:verification_status)"
                ),
                {
                    "id": recipe_id,
                    "look_version_id": look_version_id,
                    "camera_profile_id": recipe.camera_profile_id,
                    "name": recipe.name,
                    "settings": json.dumps(recipe.settings),
                    "provenance": recipe.provenance,
                    "verification_status": validation["verification_status"],
                },
            )
        return {"id": recipe_id, **recipe.model_dump(), **validation}
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/bridge/jobs/{job_id}")
def bridge_job(job_id: str):
    try:
        return get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/bridge/jobs", status_code=201)
def queue_bridge_job(job: BridgeJobInput):
    try:
        return create_job(job.job_type, job.payload, job.bridge_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc