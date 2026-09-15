from __future__ import annotations

import json
import base64
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from core.color.cube import parse_cube, parse_hald
from core.leica.parser import parse_look_payload


SUPPORTED_EXTENSIONS = {
    ".cube": "cube",
    ".dcp": "dcp",
    ".xmp": "xmp",
    ".lrtemplate": "lrtemplate",
    ".jpg": "reference_image",
    ".jpeg": "reference_image",
    ".png": "reference_image",
    ".webp": "reference_image",
    ".tif": "reference_image",
    ".tiff": "reference_image",
    ".raf": "raw_image",
    ".dng": "raw_image",
    ".bin": "leica_payload",
    ".payload": "leica_payload",
}

DCP_TAGS = {
    50721: "ColorMatrix1", 50722: "ColorMatrix2",
    50723: "CameraCalibration1", 50724: "CameraCalibration2",
    50725: "ReductionMatrix1", 50726: "ReductionMatrix2",
    50730: "BaselineExposure", 50778: "CalibrationIlluminant1",
    50779: "CalibrationIlluminant2", 50932: "ProfileCalibrationSignature",
    50936: "ProfileName", 50937: "ProfileHueSatMapDims",
    50938: "ProfileHueSatMapData1", 50939: "ProfileHueSatMapData2",
    50940: "ProfileToneCurve", 50964: "ForwardMatrix1",
    50965: "ForwardMatrix2", 50981: "ProfileLookTableDims",
    50982: "ProfileLookTableData",
}


def _tiff_tags(content: bytes) -> dict:
    """Read scalar/rational/float DCP tags without claiming full DCP support."""
    if len(content) < 8 or content[:2] not in {b"II", b"MM"}:
        raise ValueError("DCP does not have a TIFF/DNG profile header")
    endian = "<" if content[:2] == b"II" else ">"
    marker = struct.unpack_from(endian + "H", content, 2)[0]
    if marker not in {42, 0x4352}:
        raise ValueError("Unsupported TIFF header in DCP")
    offset = struct.unpack_from(endian + "I", content, 4)[0]
    if offset + 2 > len(content):
        raise ValueError("DCP TIFF directory is truncated")
    count = struct.unpack_from(endian + "H", content, offset)[0]
    types = {1: (1, "B"), 2: (1, "s"), 3: (2, "H"), 4: (4, "I"), 5: (8, "R"),
             7: (1, "B"), 9: (4, "i"), 10: (8, "r"), 11: (4, "f"), 12: (8, "d")}
    result = {}
    for index in range(count):
        pos = offset + 2 + index * 12
        if pos + 12 > len(content):
            break
        tag, kind, number = struct.unpack_from(endian + "HHI", content, pos)
        if tag not in DCP_TAGS or kind not in types:
            continue
        width, fmt = types[kind]
        size = width * number
        raw_pos = pos + 8 if size <= 4 else struct.unpack_from(endian + "I", content, pos + 8)[0]
        if raw_pos + size > len(content):
            continue
        raw = content[raw_pos:raw_pos + size]
        try:
            if kind == 2:
                value = raw.rstrip(b"\0").decode("utf-8", errors="replace")
            elif kind in {5, 10}:
                value = [float(a) / float(b) if b else 0.0
                         for a, b in struct.iter_unpack(endian + ("II" if kind == 5 else "ii"), raw)]
            elif kind == 7:
                value = {"bytes": len(raw), "sha256": __import__("hashlib").sha256(raw).hexdigest()}
            else:
                value = list(struct.unpack(endian + fmt * number, raw))
                value = value[0] if len(value) == 1 else value
            result[DCP_TAGS[tag]] = value
        except (struct.error, UnicodeError, ZeroDivisionError):
            continue
    return result


def inspect_source_asset(filename: str, content: bytes) -> dict:
    extension = Path(filename).suffix.lower()
    asset_type = "hald" if ".hald." in filename.lower() and extension in {".png", ".tif", ".tiff"} else SUPPORTED_EXTENSIONS.get(extension)
    if not asset_type:
        raise ValueError(f"Unsupported source asset extension: {extension or 'none'}")
    metadata: dict = {"extension": extension}
    if asset_type == "cube":
        metadata.update(parse_cube(content).summary())
    elif asset_type == "xmp":
        root = ET.fromstring(content)
        text = content.decode("utf-8", errors="replace")
        attributes = {}
        for element in root.iter():
            for key, value in element.attrib.items():
                attributes[key] = value
        metadata.update({"root_tag": root.tag, "xml": True, "attributes": attributes,
                         "settings": {key: value for key, value in attributes.items()
                                      if any(token in key.lower() for token in ("exposure", "contrast", "saturation",
                                                                                "temperature", "tint", "highlight", "shadow"))},
                         "has_curve": "ToneCurve" in text or "Curve" in text,
                         "characters": len(text)})
    elif asset_type == "lrtemplate":
        text = content.decode("utf-8", errors="strict")
        import re
        settings = {}
        for key, raw in re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))", text):
            settings[key] = float(raw) if "." in raw else int(raw)
        metadata.update({"format": "lua-table-text", "characters": len(text),
                         "settings": settings})
    elif asset_type == "dcp":
        try:
            tags = _tiff_tags(content)
        except ValueError as exc:
            # A valid TIFF container can omit a directory in a partial profile;
            # retain the original and report exactly what was unavailable.
            tags = {}
            metadata["parse_warning"] = str(exc)
        metadata.update({"container": "TIFF", "byte_order": "little" if content[:2] == b"II" else "big",
                         "supported_parsing": "TIFF tags only", "tags": tags})
    elif asset_type == "leica_payload":
        parsed = parse_look_payload(content, include_binary=True)
        metadata.update({"format": "Leica v1.2 payload", "name": parsed["name"],
                         "look_id": parsed["look_id"], "cube": parse_cube(parsed["cube"]).summary(),
                         "base": parsed["base"], "field_count": parsed["field_count"],
                         "embedded_cube": base64.b64encode(parsed["cube"]).decode("ascii")})
    elif asset_type == "hald":
        metadata.update(parse_hald(content).summary())
    elif asset_type == "reference_image":
        from io import BytesIO

        with Image.open(BytesIO(content)) as image:
            metadata.update({"format": image.format, "width": image.width, "height": image.height, "mode": image.mode})
    else:
        metadata.update({"format": extension.removeprefix(".").upper(), "immutable_original": True})
    components = []
    if asset_type == "cube":
        components.append({"id": "cube", "type": "cube_lut", "blendable": True,
                           "metadata": metadata})
    elif asset_type == "dcp":
        tags = metadata.get("tags", {})
        for key, value in tags.items():
            if key in {"ColorMatrix1", "ColorMatrix2", "ForwardMatrix1", "ForwardMatrix2",
                       "CameraCalibration1", "CameraCalibration2", "ReductionMatrix1", "ReductionMatrix2"}:
                components.append({"id": key, "type": "matrix", "blendable": True, "values": value})
            elif key == "ProfileToneCurve":
                points = value
                if isinstance(value, list) and len(value) % 2 == 0:
                    points = [[value[index], value[index + 1]] for index in range(0, len(value), 2)]
                components.append({"id": key, "type": "tone_curve", "blendable": True, "values": points})
            elif key in {"ProfileHueSatMapData1", "ProfileHueSatMapData2", "ProfileLookTableData"}:
                components.append({"id": key, "type": "table", "blendable": False,
                                   "reason": "DCP table interpolation is not implemented"})
    elif asset_type in {"xmp", "lrtemplate"}:
        components.append({"id": "settings", "type": "settings", "blendable": True,
                           "metadata": metadata})
        if metadata.get("has_curve") or metadata.get("settings", {}).get("ToneCurve"):
            components.append({"id": "curve", "type": "tone_curve", "blendable": True,
                               "values": metadata.get("settings", {}).get("ToneCurve", [])})
    elif asset_type == "hald":
        components.append({"id": "hald_lut", "type": "cube_lut", "blendable": True,
                           "metadata": metadata})
    elif asset_type == "leica_payload":
        components.append({"id": "cube", "type": "cube_lut", "blendable": True,
                           "metadata": {"summary": metadata.get("cube"),
                                        "embedded_base64": metadata.get("embedded_cube")}})
    return {"asset_type": asset_type, "metadata": json.loads(json.dumps(metadata)),
            "components": json.loads(json.dumps(components))}