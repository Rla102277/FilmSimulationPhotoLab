"""Immutable source library backed by production PostgreSQL or local SQLite."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Iterable

from core.assets.inspect import inspect_source_asset
from server.db.studio_repository import StudioRepository


def _default_path() -> Path:
    return Path(os.getenv("SOURCE_LIBRARY_DB", "data/source_library.sqlite3"))


class SourceLibrary:
    def __init__(self, path: str | os.PathLike[str] | None = None):
        self.path = Path(path) if path else _default_path()
        url = f"sqlite:///{self.path}" if path else None
        self.repository = StudioRepository(url=url)
        if path is None:
            self._migrate_legacy()

    def _migrate_legacy(self) -> None:
        legacy = _default_path()
        if not legacy.exists() or self.repository.engine.url.database == str(legacy):
            return
        with sqlite3.connect(legacy) as db:
            db.row_factory = sqlite3.Row
            try:
                rows = db.execute("SELECT * FROM sources").fetchall()
            except sqlite3.OperationalError:
                return
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata"))
            item["components"] = json.loads(item.pop("components"))
            self.repository.add_source(item)

    @staticmethod
    def _public(row: dict, include_content: bool = False) -> dict:
        item = dict(row)
        content = item.pop("content", None)
        if content and item["asset_type"] in {"dcp", "xmp", "lrtemplate"}:
            inspection = inspect_source_asset(item["filename"], content)
            item["metadata"] = inspection["metadata"]
            item["components"] = [{**component, "provenance": {"source_id": item["id"],
                "source_sha256": item["sha256"], "filename": item["filename"],
                "component_id": component["id"]}} for component in inspection["components"]]
        item["immutable"] = True
        return {**item, **({"content": content} if include_content else {})}

    def add(self, filename: str, content: bytes, media_type: str | None = None,
            provenance: str | dict | None = None) -> dict:
        if not content:
            raise ValueError("Source file cannot be empty")
        inspection = inspect_source_asset(filename, content)
        digest = hashlib.sha256(content).hexdigest()
        existing = self.repository.source_by_sha(digest)
        if existing:
                result = self._public(existing)
                result["duplicate"] = True
                return result
        source_id = str(uuid.uuid4())
        provenance_value = provenance if isinstance(provenance, str) else json.dumps(provenance or {}, sort_keys=True)
        components = [{**component, "provenance": {
            "source_id": source_id, "source_sha256": digest,
            "filename": filename or "unnamed", "component_id": component.get("id"),
        }} for component in inspection.get("components", [])]
        item = {
            "id": source_id, "sha256": digest, "filename": filename or "unnamed",
            "media_type": media_type or "application/octet-stream", "asset_type": inspection["asset_type"],
            "size": len(content), "provenance": provenance_value,
            "metadata": inspection["metadata"], "components": components, "content": content,
        }
        if not self.repository.add_source(item):
            result = self._public(self.repository.source_by_sha(digest))
            result["duplicate"] = True
            return result
        return {**self._public(item), "duplicate": False}

    def bulk_add(self, files: Iterable[tuple[str, bytes, str | None]],
                 provenance: str | dict | None = None) -> list[dict]:
        return [self.add(name, content, media_type, provenance) for name, content, media_type in files]

    def list(self, search: str | None = None, asset_type: str | None = None) -> list[dict]:
        items = self.repository.list_sources()
        if asset_type:
            items = [item for item in items if item["asset_type"].lower() == asset_type.lower()]
        if search:
            needle = search.lower()
            items = [item for item in items if needle in str(item).lower()]
        return [self._public(item) for item in items]

    def get(self, source_id: str, include_content: bool = False) -> dict | None:
        row = self.repository.source(source_id)
        return self._public(row, include_content) if row else None

    def get_by_sha256(self, digest: str) -> dict | None:
        row = self.repository.source_by_sha(digest)
        return self._public(row) if row else None