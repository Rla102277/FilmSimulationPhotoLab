"""Persistent local source library.

The library is intentionally independent from the application's PostgreSQL
schema.  It uses SQLite plus immutable BLOBs, which provides a safe fallback
for local development while retaining persistence when DATABASE_URL is not
available.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Iterable

from core.assets.inspect import inspect_source_asset


def _default_path() -> Path:
    return Path(os.getenv("SOURCE_LIBRARY_DB", "data/source_library.sqlite3"))


class SourceLibrary:
    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path) if path else _default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL, filename TEXT NOT NULL,
                media_type TEXT NOT NULL, asset_type TEXT NOT NULL, size INTEGER NOT NULL,
                provenance TEXT NOT NULL, metadata TEXT NOT NULL, components TEXT NOT NULL,
                content BLOB NOT NULL, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(asset_type)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_sources_sha ON sources(sha256)")

    @staticmethod
    def _public(row: sqlite3.Row, include_content: bool = False) -> dict:
        item = dict(row)
        for key in ("metadata", "components"):
            item[key] = json.loads(item[key])
        inspection = inspect_source_asset(item["filename"], row["content"])
        item["metadata"] = inspection["metadata"]
        item["components"] = inspection["components"]
        item["asset_type"] = inspection["asset_type"]
        item.pop("content", None)
        item["immutable"] = True
        if not include_content:
            return item
        return {**item, "content": row["content"]}

    def add(self, filename: str, content: bytes, media_type: str | None = None,
            provenance: str | dict | None = None) -> dict:
        if not content:
            raise ValueError("Source file cannot be empty")
        inspection = inspect_source_asset(filename, content)
        digest = hashlib.sha256(content).hexdigest()
        with self._lock, self._connection() as db:
            existing = db.execute("SELECT * FROM sources WHERE sha256=?", (digest,)).fetchone()
            if existing:
                result = self._public(existing)
                result["duplicate"] = True
                return result
            source_id = str(uuid.uuid4())
            if isinstance(provenance, str):
                provenance_value = provenance
            else:
                provenance_value = json.dumps(provenance or {}, sort_keys=True)
            components = []
            for component in inspection.get("components", []):
                components.append({
                    **component,
                    "provenance": {
                        "source_id": source_id, "source_sha256": digest,
                        "filename": filename or "unnamed",
                        "component_id": component.get("id"),
                    },
                })
            db.execute(
                """INSERT INTO sources
                (id,sha256,filename,media_type,asset_type,size,provenance,metadata,components,content)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (source_id, digest, filename or "unnamed", media_type or "application/octet-stream",
                 inspection["asset_type"], len(content), provenance_value,
                 json.dumps(inspection["metadata"], sort_keys=True),
                 json.dumps(components, sort_keys=True), content),
            )
            result = {
                "id": source_id, "sha256": digest, "filename": filename or "unnamed",
                "media_type": media_type or "application/octet-stream", "asset_type": inspection["asset_type"],
                "size": len(content), "provenance": provenance_value,
                "metadata": inspection["metadata"], "components": components,
                "duplicate": False, "immutable": True,
            }
            return result

    def bulk_add(self, files: Iterable[tuple[str, bytes, str | None]],
                 provenance: str | dict | None = None) -> list[dict]:
        return [self.add(name, content, media_type, provenance) for name, content, media_type in files]

    def list(self, search: str | None = None, asset_type: str | None = None) -> list[dict]:
        query = "SELECT * FROM sources"
        clauses: list[str] = []
        args: list[str] = []
        if asset_type:
            clauses.append("lower(asset_type)=lower(?)")
            args.append(asset_type)
        if search:
            clauses.append("(lower(filename) LIKE ? OR lower(provenance) LIKE ? OR lower(metadata) LIKE ? OR lower(components) LIKE ?)")
            needle = f"%{search.lower()}%"
            args.extend([needle] * 4)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY imported_at DESC, filename ASC"
        with self._connection() as db:
            return [self._public(row) for row in db.execute(query, args).fetchall()]

    def get(self, source_id: str, include_content: bool = False) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            return self._public(row, include_content) if row else None

    def get_by_sha256(self, digest: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT * FROM sources WHERE sha256=?", (digest,)).fetchone()
            return self._public(row) if row else None