from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from core.color.cube import parse_cube


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
}


def inspect_source_asset(filename: str, content: bytes) -> dict:
    extension = Path(filename).suffix.lower()
    asset_type = SUPPORTED_EXTENSIONS.get(extension)
    if not asset_type:
        raise ValueError(f"Unsupported source asset extension: {extension or 'none'}")
    metadata: dict = {"extension": extension}
    if asset_type == "cube":
        metadata.update(parse_cube(content).summary())
    elif asset_type == "xmp":
        root = ET.fromstring(content)
        metadata.update({"root_tag": root.tag, "xml": True})
    elif asset_type == "lrtemplate":
        text = content.decode("utf-8", errors="strict")
        metadata.update({"format": "lua-table-text", "characters": len(text)})
    elif asset_type == "dcp":
        if content[:4] not in {b"II*\x00", b"MM\x00*"}:
            raise ValueError("DCP does not have a TIFF/DNG profile header")
        metadata.update({"container": "TIFF", "byte_order": "little" if content[:2] == b"II" else "big"})
    elif asset_type == "reference_image":
        from io import BytesIO

        with Image.open(BytesIO(content)) as image:
            metadata.update({"format": image.format, "width": image.width, "height": image.height, "mode": image.mode})
    else:
        metadata.update({"format": extension.removeprefix(".").upper(), "immutable_original": True})
    return {"asset_type": asset_type, "metadata": json.loads(json.dumps(metadata))}