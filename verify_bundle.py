#!/usr/bin/env python3
"""Offline integrity validation for the Replit migration bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip"
WORKING = ROOT / "working/Infinite_Arch_Leica_Looks_v1.2"
EXPECTED_ARCHIVE_SHA256 = (
    "1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate() -> list[dict]:
    if sha256(ARCHIVE) != EXPECTED_ARCHIVE_SHA256:
        raise RuntimeError("authoritative v1.2 archive hash mismatch")

    manifest_path = WORKING / "looks_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest) != 9:
        raise RuntimeError(f"expected nine Looks, found {len(manifest)}")

    expected_ids = list(range(1001, 1010))
    actual_ids = [entry["id"] for entry in manifest]
    if actual_ids != expected_ids:
        raise RuntimeError(f"unexpected Look IDs: {actual_ids}")

    for entry in manifest:
        cube = WORKING / entry["cube"]
        icon = WORKING / entry["icon"]
        if cube.stat().st_size != entry["cube_bytes"]:
            raise RuntimeError(f"CUBE size mismatch: {cube}")
        if icon.stat().st_size != entry["icon_bytes"]:
            raise RuntimeError(f"icon size mismatch: {icon}")
        if sha256(cube) != entry["cube_sha256"]:
            raise RuntimeError(f"CUBE hash mismatch: {cube}")
        if sha256(icon) != entry["icon_sha256"]:
            raise RuntimeError(f"icon hash mismatch: {icon}")

        rows = 0
        for raw_line in cube.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.upper().startswith(
                ("TITLE", "LUT_3D_SIZE", "DOMAIN_MIN", "DOMAIN_MAX")
            ):
                continue
            values = [float(value) for value in line.split()]
            if len(values) != 3 or any(value < 0 or value > 1 for value in values):
                raise RuntimeError(f"invalid CUBE row in {cube}: {line}")
            rows += 1
        if rows != 17**3:
            raise RuntimeError(f"expected 4913 CUBE rows in {cube}, found {rows}")

    return manifest


if __name__ == "__main__":
    validated = validate()
    print("PASS: authoritative Infinite Arch Leica Looks v1.2 is intact")
    for look in validated:
        print(f"{look['id']}  {look['name']}  base={look['base_name']}")

