from __future__ import annotations

import struct

from core.leica.fields import DEFAULT_MARKER
from core.leica.validator import validate_components, verify_compiled_payload


def _prefix(marker: int, prop: int, dtype: int) -> bytes:
    return struct.pack("<IHH", marker, prop, dtype)


def _uint32(marker: int, prop: int, value: int) -> bytes:
    return _prefix(marker, prop, 0x0006) + struct.pack("<I", value)


def _string(marker: int, prop: int, value: str) -> bytes:
    encoded = value.encode("utf-16le")
    return _prefix(marker, prop, 0xFFFF) + bytes([len(encoded) // 2 + 1]) + encoded + b"\0\0"


def _bytes(marker: int, prop: int, value: bytes) -> bytes:
    return _prefix(marker, prop, 0x4002) + struct.pack("<I", len(value)) + value


def compile_look_payload(
    look_id: int,
    name: str,
    icon: bytes,
    cube: bytes,
    d864: int = 2,
    base: int = 0,
    marker: int = DEFAULT_MARKER,
) -> tuple[bytes, dict]:
    validated = validate_components(look_id, name, icon, cube, d864, base)
    requested = {"look_id": look_id, "name": validated["name"], "icon": icon, "cube": cube, "d864": d864, "base": base}
    payload = b"".join((
        struct.pack("<I", 6),
        _uint32(marker, 0xD861, look_id),
        _string(marker, 0xDC44, validated["name"]),
        _bytes(marker, 0xDC86, icon),
        _bytes(marker, 0xD860, cube),
        _uint32(marker, 0xD864, d864),
        _uint32(marker, 0xD866, base),
    ))
    verification = verify_compiled_payload(payload, requested)
    if not verification["valid"]:
        raise RuntimeError(f"Compile/parse verification failed: {verification['checks']}")
    return payload, {"components": validated, "verification": verification["checks"]}