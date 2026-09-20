from __future__ import annotations

import io
import json
import uuid
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from server.auth import require_user
from server.db.database import engine
from server.api.studio import build_graph_package_bytes


router = APIRouter(prefix="/studio", tags=["studio-workspaces"])


class SavedGraph(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    graph: dict


class PackageSelection(BaseModel):
    look_ids: list[str] = Field(min_length=1, max_length=9)


def _rows(statement, params: dict) -> list[dict]:
    with engine.begin() as connection:
        return [dict(row) for row in connection.execute(statement, params).mappings()]


@router.get("/workspaces")
def list_workspaces(user_id: str = Depends(require_user)):
    return _rows(text("""
        SELECT id::text, name, graph, created_at, updated_at
        FROM studio_workspaces WHERE owner_id=:owner_id ORDER BY updated_at DESC
    """), {"owner_id": user_id})


@router.post("/workspaces", status_code=201)
def save_workspace(payload: SavedGraph, user_id: str = Depends(require_user)):
    workspace_id = str(uuid.uuid4())
    return _rows(text("""
        INSERT INTO studio_workspaces(id, owner_id, name, graph)
        VALUES (CAST(:id AS UUID), :owner_id, :name, CAST(:graph AS JSONB))
        RETURNING id::text, name, graph, created_at, updated_at
    """), {"id": workspace_id, "owner_id": user_id, "name": payload.name,
           "graph": json.dumps(payload.graph)})[0]


@router.put("/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, payload: SavedGraph, user_id: str = Depends(require_user)):
    rows = _rows(text("""
        UPDATE studio_workspaces SET name=:name, graph=CAST(:graph AS JSONB), updated_at=now()
        WHERE id=CAST(:id AS UUID) AND owner_id=:owner_id
        RETURNING id::text, name, graph, created_at, updated_at
    """), {"id": workspace_id, "owner_id": user_id, "name": payload.name,
           "graph": json.dumps(payload.graph)})
    if not rows:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return rows[0]


@router.delete("/workspaces/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: str, user_id: str = Depends(require_user)):
    rows = _rows(text("""
        DELETE FROM studio_workspaces WHERE id=CAST(:id AS UUID) AND owner_id=:owner_id
        RETURNING id
    """), {"id": workspace_id, "owner_id": user_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.get("/looks")
def list_looks(user_id: str = Depends(require_user)):
    return _rows(text("""
        SELECT id::text, name, graph, created_at, updated_at
        FROM studio_looks WHERE owner_id=:owner_id ORDER BY updated_at DESC
    """), {"owner_id": user_id})


@router.post("/looks", status_code=201)
def save_look(payload: SavedGraph, user_id: str = Depends(require_user)):
    look_id = str(uuid.uuid4())
    return _rows(text("""
        INSERT INTO studio_looks(id, owner_id, name, graph)
        VALUES (CAST(:id AS UUID), :owner_id, :name, CAST(:graph AS JSONB))
        RETURNING id::text, name, graph, created_at, updated_at
    """), {"id": look_id, "owner_id": user_id, "name": payload.name,
           "graph": json.dumps(payload.graph)})[0]


@router.delete("/looks/{look_id}", status_code=204)
def delete_look(look_id: str, user_id: str = Depends(require_user)):
    rows = _rows(text("""
        DELETE FROM studio_looks WHERE id=CAST(:id AS UUID) AND owner_id=:owner_id
        RETURNING id
    """), {"id": look_id, "owner_id": user_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Look not found")


@router.post("/looks/package")
def package_looks(payload: PackageSelection, user_id: str = Depends(require_user)):
    if len(set(payload.look_ids)) != len(payload.look_ids):
        raise HTTPException(status_code=422, detail="Select each Look only once")
    rows = _rows(text("""
        SELECT id::text, name, graph FROM studio_looks
        WHERE owner_id=:owner_id AND id = ANY(CAST(:ids AS UUID[]))
    """), {"owner_id": user_id, "ids": payload.look_ids})
    if len(rows) != len(payload.look_ids):
        raise HTTPException(status_code=404, detail="One or more selected Looks were not found")
    by_id = {row["id"]: row for row in rows}
    output = io.BytesIO()
    manifest = []
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, look_id in enumerate(payload.look_ids, start=1):
            row = by_id[look_id]
            graph = dict(row["graph"])
            graph["name"] = row["name"]
            package = build_graph_package_bytes(graph)
            filename = f"{index:02d}-{row['name'].replace('/', '-')}.zip"
            archive.writestr(filename, package)
            manifest.append({"id": look_id, "name": row["name"], "package": filename})
        archive.writestr("selected-looks.json", json.dumps(manifest, indent=2))
    return Response(output.getvalue(), media_type="application/zip", headers={
        "Content-Disposition": 'attachment; filename="film-look-studio-selection.zip"',
    })