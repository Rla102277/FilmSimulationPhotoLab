from __future__ import annotations

import hashlib
import struct

from core.leica.authoritative import get_authoritative_look, read_look_asset


WIDTHS = {1: 1, 2: 1, 3: 2, 4: 2, 5: 4, 6: 4, 7: 8, 8: 8, 9: 16, 10: 16}
PROPERTY_NAMES = {
    0xD861: "look_id",
    0xDC44: "name",
    0xDC86: "icon",
    0xD860: "cube",
    0xD864: "type",
    0xD866: "base",
}


def _prefix(marker: int, prop: int, dtype: int) -> bytes:
    return struct.pack("<IHH", marker, prop, dtype)


def _uint32(marker: int, prop: int, value: int) -> bytes:
    return _prefix(marker, prop, 0x0006) + struct.pack("<I", value)


def _string(marker: int, prop: int, value: str) -> bytes:
    encoded = value.encode("utf-16le")
    return _prefix(marker, prop, 0xFFFF) + bytes([len(encoded) // 2 + 1]) + encoded + b"\0\0"


def _bytes(marker: int, prop: int, value: bytes) -> bytes:
    return _prefix(marker, prop, 0x4002) + struct.pack("<I", len(value)) + value


def build_authoritative_payload(look_id: int, marker: int = 0x20000014) -> bytes:
    look = get_authoritative_look(look_id)
    cube = read_look_asset(look_id, "cube")
    icon = read_look_asset(look_id, "icon")
    payload = b"".join(
        (
            struct.pack("<I", 6),
            _uint32(marker, 0xD861, look["id"]),
            _string(marker, 0xDC44, look["name"]),
            _bytes(marker, 0xDC86, icon),
            _bytes(marker, 0xD860, cube),
            _uint32(marker, 0xD864, 2),
            _uint32(marker, 0xD866, look["base"]),
        )
    )
    parsed = inspect_payload(payload)
    if parsed["field_count"] != 6 or parsed["look_id"] != look_id:
        raise RuntimeError("Generated payload did not pass local decode validation")
    return payload


def inspect_payload(payload: bytes) -> dict:
    if len(payload) < 4:
        raise ValueError("Payload is too short")
    count = struct.unpack_from("<I", payload)[0]
    offset = 4
    result: dict = {"field_count": count, "fields": [], "bytes": len(payload)}
    for _ in range(count):
        marker, prop, dtype = struct.unpack_from("<IHH", payload, offset)
        offset += 8
        if dtype in WIDTHS:
            width = WIDTHS[dtype]
            value = int.from_bytes(payload[offset : offset + width], "little")
            offset += width
        elif dtype == 0xFFFF:
            units = payload[offset]
            offset += 1
            raw = payload[offset : offset + units * 2]
            offset += units * 2
            value = raw[:-2].decode("utf-16le")
        elif dtype == 0x4002:
            length = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            raw = payload[offset : offset + length]
            offset += length
            value = {"bytes": length, "sha256": hashlib.sha256(raw).hexdigest()}
        else:
            raise ValueError(f"Unsupported payload datatype 0x{dtype:04X}")
        name = PROPERTY_NAMES.get(prop, f"0x{prop:04X}")
        result["fields"].append(
            {"marker": f"0x{marker:08X}", "property": f"0x{prop:04X}", "name": name, "value": value}
        )
        if name in {"look_id", "name", "type", "base"}:
            result[name] = value
    if offset != len(payload):
        raise ValueError("Payload has trailing or malformed bytes")
    result["sha256"] = hashlib.sha256(payload).hexdigest()
    return result