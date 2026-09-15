from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import LargeBinary, MetaData, Table, Column, Integer, String, Text, UniqueConstraint, create_engine, insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError


metadata = MetaData()

sources = Table(
    "studio_sources", metadata,
    Column("id", String(36), primary_key=True),
    Column("sha256", String(64), unique=True, nullable=False),
    Column("filename", Text, nullable=False),
    Column("media_type", Text, nullable=False),
    Column("asset_type", Text, nullable=False),
    Column("size", Integer, nullable=False),
    Column("provenance", Text, nullable=False),
    Column("metadata_json", Text, nullable=False),
    Column("components_json", Text, nullable=False),
    Column("content", LargeBinary, nullable=False),
    Column("imported_at", String(40), nullable=False),
)

looks = Table(
    "studio_looks", metadata,
    Column("id", String(36), primary_key=True),
    Column("name", Text, nullable=False),
    Column("status", String(20), nullable=False),
    Column("tags_json", Text, nullable=False),
    Column("notes", Text, nullable=False),
    Column("rating", Integer, nullable=True),
    Column("favorite", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("updated_at", String(40), nullable=False),
)

look_versions = Table(
    "studio_look_versions", metadata,
    Column("id", String(36), primary_key=True),
    Column("look_id", String(36), nullable=False, index=True),
    Column("number", Integer, nullable=False),
    Column("label", String(30), nullable=False),
    Column("graph_json", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
    UniqueConstraint("look_id", "number", name="uq_studio_look_version"),
)

snapshots = Table(
    "studio_snapshots", metadata,
    Column("id", String(36), primary_key=True),
    Column("look_id", String(36), nullable=False, index=True),
    Column("name", Text, nullable=False),
    Column("graph_json", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
)

workspace = Table(
    "studio_workspace", metadata,
    Column("id", String(20), primary_key=True),
    Column("state_json", Text, nullable=False),
    Column("updated_at", String(40), nullable=False),
)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _url(url: str | None = None) -> str:
    value = url or os.getenv("DATABASE_URL")
    if value:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value
    path = Path(os.getenv("STUDIO_DB", "data/studio.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


class WorkspaceConflict(RuntimeError):
    def __init__(self, revision: int):
        self.revision = revision
        super().__init__(f"Workspace revision conflict; current revision is {revision}")


class StudioRepository:
    def __init__(self, url: str | None = None, engine: Engine | None = None):
        self.engine = engine or create_engine(_url(url), pool_pre_ping=True)
        metadata.create_all(self.engine)
        self._write_lock = threading.RLock()
        with self.engine.begin() as db:
            db.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_studio_look_version "
                "ON studio_look_versions (look_id, number)"
            )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _decode(row: Any) -> dict:
        item = dict(row._mapping if hasattr(row, "_mapping") else row)
        for source, target in (
            ("metadata_json", "metadata"), ("components_json", "components"),
            ("tags_json", "tags"), ("graph_json", "graph"), ("state_json", "state"),
        ):
            if source in item:
                item[target] = json.loads(item.pop(source))
        if "favorite" in item:
            item["favorite"] = bool(item["favorite"])
        return item

    def source_by_sha(self, digest: str) -> dict | None:
        with self.engine.connect() as db:
            row = db.execute(select(sources).where(sources.c.sha256 == digest)).first()
            return self._decode(row) if row else None

    def add_source(self, item: dict) -> bool:
        values = dict(item)
        values["metadata_json"] = self._json(values.pop("metadata"))
        values["components_json"] = self._json(values.pop("components"))
        values.setdefault("imported_at", _now())
        with self._write_lock:
            try:
                with self.engine.begin() as db:
                    db.execute(insert(sources).values(**values))
                return True
            except IntegrityError:
                if self.source_by_sha(values["sha256"]):
                    return False
                raise

    def list_sources(self) -> list[dict]:
        with self.engine.connect() as db:
            return [self._decode(row) for row in db.execute(
                select(sources).order_by(sources.c.imported_at.desc(), sources.c.filename)
            )]

    def source(self, source_id: str) -> dict | None:
        with self.engine.connect() as db:
            row = db.execute(select(sources).where(sources.c.id == source_id)).first()
            return self._decode(row) if row else None

    def save_look(self, payload: dict) -> dict:
        now = _now()
        look_id = str(payload.get("id") or uuid.uuid4())
        graph = dict(payload["graph"])
        with self._write_lock:
            with self.engine.begin() as db:
                current = db.execute(
                    select(looks).where(looks.c.id == look_id).with_for_update()
                ).first()
                metadata_values = {
                    "name": str(payload.get("name") or graph.get("name") or "Untitled Look"),
                    "status": payload.get("status", "draft"),
                    "tags_json": self._json(payload.get("tags", [])),
                    "notes": str(payload.get("notes", "")),
                    "rating": payload.get("rating"),
                    "favorite": int(bool(payload.get("favorite", False))),
                    "updated_at": now,
                }
                if current:
                    db.execute(update(looks).where(looks.c.id == look_id).values(**metadata_values))
                else:
                    db.execute(insert(looks).values(id=look_id, created_at=now, **metadata_values))
                number = int(db.execute(
                    select(look_versions.c.number).where(look_versions.c.look_id == look_id)
                    .order_by(look_versions.c.number.desc()).limit(1)
                ).scalar() or 0) + 1
                graph["version"] = f"v1.{number}"
                db.execute(insert(look_versions).values(
                    id=str(uuid.uuid4()), look_id=look_id, number=number,
                    label=f"v1.{number}", graph_json=self._json(graph), created_at=now,
                ))
        return self.get_look(look_id)

    def list_looks(self) -> list[dict]:
        with self.engine.connect() as db:
            rows = db.execute(select(looks).order_by(looks.c.updated_at.desc())).fetchall()
        return [self._look_summary(row) for row in rows]

    def _look_summary(self, row: Any) -> dict:
        item = self._decode(row)
        with self.engine.connect() as db:
            version = db.execute(
                select(look_versions).where(look_versions.c.look_id == item["id"])
                .order_by(look_versions.c.number.desc()).limit(1)
            ).first()
        if version:
            decoded = self._decode(version)
            item["version"] = decoded["label"]
            item["graph"] = decoded["graph"]
        return item

    def get_look(self, look_id: str) -> dict:
        with self.engine.connect() as db:
            row = db.execute(select(looks).where(looks.c.id == look_id)).first()
            versions = db.execute(
                select(look_versions).where(look_versions.c.look_id == look_id)
                .order_by(look_versions.c.number.desc())
            ).fetchall()
            saved_snapshots = db.execute(
                select(snapshots).where(snapshots.c.look_id == look_id)
                .order_by(snapshots.c.created_at)
            ).fetchall()
        if not row:
            raise KeyError(look_id)
        result = self._decode(row)
        result["versions"] = [self._decode(item) for item in versions]
        result["snapshots"] = [self._decode(item) for item in saved_snapshots]
        if result["versions"]:
            result["version"] = result["versions"][0]["label"]
            result["graph"] = result["versions"][0]["graph"]
        return result

    def add_snapshot(self, look_id: str, name: str, graph: dict) -> dict:
        item = {"id": str(uuid.uuid4()), "look_id": look_id, "name": name,
                "graph_json": self._json(graph), "created_at": _now()}
        with self.engine.begin() as db:
            if not db.execute(select(looks.c.id).where(looks.c.id == look_id)).first():
                raise KeyError(look_id)
            db.execute(insert(snapshots).values(**item))
        return self._decode(item)

    def save_workspace(self, state: dict, expected_revision: int) -> dict:
        with self._write_lock:
            with self.engine.begin() as db:
                existing = db.execute(
                    select(workspace).where(workspace.c.id == "active").with_for_update()
                ).first()
                current_revision = 0
                if existing:
                    current = self._decode(existing)["state"]
                    current_revision = int(current.get("revision", 0))
                if expected_revision != current_revision:
                    same_client = (
                        existing and state.get("client_id") and
                        state.get("client_id") == current.get("client_id")
                    )
                    newer_operation = int(state.get("client_sequence", 0)) > int(
                        current.get("client_sequence", 0)
                    )
                    if same_client and not newer_operation:
                        return {"state": current, "updated_at": dict(existing._mapping)["updated_at"]}
                    if not (same_client and newer_operation):
                        raise WorkspaceConflict(current_revision)
                state["revision"] = current_revision + 1
                values = {"state_json": self._json(state), "updated_at": _now()}
                if existing:
                    db.execute(update(workspace).where(workspace.c.id == "active").values(**values))
                else:
                    db.execute(insert(workspace).values(id="active", **values))
        return {"state": state, "updated_at": values["updated_at"]}

    def get_workspace(self) -> dict | None:
        with self.engine.connect() as db:
            row = db.execute(select(workspace).where(workspace.c.id == "active")).first()
            return self._decode(row) if row else None