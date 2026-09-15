"""Lazy catalog for the uploaded DCP/CUBE master archive."""

from __future__ import annotations

import hashlib
import os
import re
import zipfile
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARCHIVE = ROOT / "attached_assets" / "0_ALL_DCP_CUBE_LIBRARY_1789502493370.zip"
SUPPORTED = {".dcp": "dcp", ".cube": "cube"}


def _archive_path() -> Path:
    return Path(os.getenv("PROFILE_LIBRARY_ARCHIVE", str(DEFAULT_ARCHIVE)))


def _neutral_name(member: str) -> str:
    name = PurePosixPath(member).stem
    camera_prefixes = (
        r"Canon EOS 5D\s+",
        r"LEICA M \(Typ 240\)\s+",
        r"M9 Digital Camera\s+",
    )
    for prefix in camera_prefixes:
        name = re.sub(rf"^{prefix}", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*-\s*L$", "", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).strip()


@lru_cache(maxsize=1)
def catalog() -> tuple[dict, ...]:
    archive = _archive_path()
    if not archive.exists():
        return ()
    raw = []
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            extension = PurePosixPath(info.filename).suffix.lower()
            if info.is_dir() or extension not in SUPPORTED:
                continue
            raw.append({
                "catalog_id": hashlib.sha256(info.filename.encode()).hexdigest()[:20],
                "member": info.filename,
                "asset_type": SUPPORTED[extension],
                "display_name": _neutral_name(info.filename),
                "size": info.file_size,
            })
    totals = Counter((item["asset_type"], item["display_name"].lower()) for item in raw)
    seen: defaultdict[tuple[str, str], int] = defaultdict(int)
    for item in raw:
        key = (item["asset_type"], item["display_name"].lower())
        seen[key] += 1
        if totals[key] > 1:
            item["display_name"] = f'{item["display_name"]} · Variant {seen[key]}'
    return tuple(raw)


def find_profile(catalog_id: str) -> dict | None:
    return next((dict(item) for item in catalog() if item["catalog_id"] == catalog_id), None)


def read_profile(profile: dict) -> bytes:
    with zipfile.ZipFile(_archive_path()) as bundle:
        return bundle.read(profile["member"])