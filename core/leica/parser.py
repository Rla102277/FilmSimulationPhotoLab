from __future__ import annotations

import hashlib
import struct

from core.color.cube import parse_cube
from core.leica.fields import FIELD_NAMES, FIELD_ORDER, FIELD_TYPES

WIDTHS = {1: 1, 2: 1, 3: 2, 4: 2, 5: 4, 6: 4, 7: 8, 8: 8, 9: 16, 10: 16}


def parse_look_payload(payload: bytes, include_binary: bool = False) -> dict:
    if len(payload) < 4:
        raise ValueError("Payload is too short")
    count = struct.unpack_from("<I", payload)[0]
    if count != 6:
        raise ValueError(f"Expected six Leica properties, found {count}")
    offset = 4
    fields = []
    values: dict = {}
    for _ in range(count):
        if offset + 8 > len(payload):
            raise ValueError("Payload field header is truncated")
        marker, prop, dtype = struct.unpack_from("<IHH", payload, offset)
        offset += 8
        if dtype in WIDTHS:
            width = WIDTHS[dtype]
            if offset + width > len(payload):
                raise ValueError("Numeric field is truncated")
            value = int.from_bytes(payload[offset : offset + width], "little")
            raw = payload[offset : offset + width]
            offset += width
        elif dtype == 0xFFFF:
            if offset >= len(payload):
                raise ValueError("String length is missing")
            units = payload[offset]
            offset += 1
            raw = payload[offset : offset + units * 2]
            if len(raw) != units * 2 or not raw.endswith(b"\0\0"):
                raise ValueError("UTF-16LE Leica name is malformed")
            offset += units * 2
            value = raw[:-2].decode("utf-16le")
        elif dtype == 0x4002:
            if offset + 4 > len(payload):
                raise ValueError("Binary field length is missing")
            length = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            raw = payload[offset : offset + length]
            if len(raw) != length:
                raise ValueError("Binary field is truncated")
            offset += length
            value = raw if include_binary else {"bytes": length, "sha256": hashlib.sha256(raw).hexdigest()}
        else:
            raise ValueError(f"Unsupported payload datatype 0x{dtype:04X}")
        name = FIELD_NAMES.get(prop, f"0x{prop:04X}")
        fields.append({
            "marker": f"0x{marker:08X}",
            "property": f"0x{prop:04X}",
            "datatype": f"0x{dtype:04X}",
            "name": name,
            "value": value,
        })
        values[name] = value
    if offset != len(payload):
        raise ValueError("Payload has trailing bytes")
    if tuple(int(field["property"], 16) for field in fields) != FIELD_ORDER:
        raise ValueError("Leica fields are not in the authoritative v1.2 order")
    for field in fields:
        prop = int(field["property"], 16)
        if int(field["datatype"], 16) != FIELD_TYPES[prop]:
            raise ValueError(f"{field['property']} has datatype {field['datatype']}; expected 0x{FIELD_TYPES[prop]:04X}")
    markers = {field["marker"] for field in fields}
    if len(markers) != 1:
        raise ValueError("All Leica properties must use the same record marker")
    result = {"field_count": count, "fields": fields, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), **values}
    if include_binary:
        result["cube_summary"] = parse_cube(values["cube"]).summary()
        result["icon_summary"] = {
            "bytes": len(values["icon"]),
            "sha256": hashlib.sha256(values["icon"]).hexdigest(),
            "bmp_header": values["icon"][:2] == b"BM",
        }
    return result