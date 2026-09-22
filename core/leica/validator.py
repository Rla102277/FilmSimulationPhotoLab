from __future__ import annotations

import hashlib
import struct

from core.color.cube import parse_cube
from core.leica.fields import AUTHORITATIVE_BASES, AUTHORITATIVE_D864, FIELD_ORDER
from core.leica.parser import parse_look_payload


def validate_components(look_id: int, name: str, icon: bytes, cube: bytes, d864: int, base: int) -> dict:
    if not 1000 <= look_id <= 0xFFFFFFFF:
        raise ValueError("Custom Leica Look ID must be between 1000 and 4294967295")
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Look name is required")
    if len(clean_name.encode("utf-16le")) // 2 + 1 > 255:
        raise ValueError("Look name is too long for the authoritative one-byte UTF-16 length")
    if len(icon) != 2224 or not icon.startswith(b"BM"):
        raise ValueError("DC86 icon data must be a BMP asset")
    width, height = struct.unpack_from("<ii", icon, 18)
    bits = struct.unpack_from("<H", icon, 28)[0]
    if (width, height, bits) != (180, 90, 1):
        raise ValueError("DC86 icon must be a 180×90, 1-bit BMP")
    cube_summary = parse_cube(cube).summary()
    if cube_summary["size"] != 17:
        raise ValueError("D860 must contain a Leica 17-cube")
    rows = parse_cube(cube).values
    if (rows < 0).any() or (rows > 1).any():
        raise ValueError("Leica D860 output values must be bounded to 0..1")
    is_monochrome = bool(((abs(rows[:, 0] - rows[:, 1]) < 1e-9) & (abs(rows[:, 1] - rows[:, 2]) < 1e-9)).all())
    if is_monochrome != (base == 1):
        raise ValueError("D860 color/monochrome content must match D866 base")
    if d864 != AUTHORITATIVE_D864:
        raise ValueError(f"D864 must remain {AUTHORITATIVE_D864}, the authoritative v1.2 value")
    if base not in AUTHORITATIVE_BASES:
        raise ValueError("D866 base must be 0 (Standard) or 1 (Monochrome)")
    return {
        "look_id": look_id,
        "name": clean_name,
        "d864": d864,
        "base": base,
        "base_name": AUTHORITATIVE_BASES[base],
        "icon": {"bytes": len(icon), "sha256": hashlib.sha256(icon).hexdigest()},
        "cube": cube_summary | {"sha256": hashlib.sha256(cube).hexdigest()},
    }


def verify_compiled_payload(payload: bytes, requested: dict) -> dict:
    parsed = parse_look_payload(payload, include_binary=True)
    checks = {
        "field_order": tuple(int(field["property"], 16) for field in parsed["fields"]) == FIELD_ORDER,
        "look_id": parsed["look_id"] == requested["look_id"],
        "name": parsed["name"] == requested["name"],
        "icon_sha256": hashlib.sha256(parsed["icon"]).hexdigest() == hashlib.sha256(requested["icon"]).hexdigest(),
        "cube_sha256": hashlib.sha256(parsed["cube"]).hexdigest() == hashlib.sha256(requested["cube"]).hexdigest(),
        "d864": parsed["type"] == requested["d864"],
        "base": parsed["base"] == requested["base"],
    }
    return {"valid": all(checks.values()), "checks": checks, "parsed": parsed}
