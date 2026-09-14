from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class CubeLUT:
    title: str
    size: int
    domain_min: tuple[float, float, float]
    domain_max: tuple[float, float, float]
    values: np.ndarray

    def summary(self) -> dict:
        return {
            "title": self.title,
            "size": self.size,
            "rows": int(self.values.shape[0]),
            "domain_min": self.domain_min,
            "domain_max": self.domain_max,
            "value_min": float(self.values.min()),
            "value_max": float(self.values.max()),
            "order": "red-fast",
        }


def parse_cube(data: bytes) -> CubeLUT:
    text = data.decode("ascii", errors="strict")
    title = ""
    size = None
    domain_min = (0.0, 0.0, 0.0)
    domain_max = (1.0, 1.0, 1.0)
    rows: list[tuple[float, float, float]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        keyword = parts[0].upper()
        if keyword == "TITLE":
            title = line.partition(" ")[2].strip().strip('"')
        elif keyword == "LUT_3D_SIZE":
            size = int(parts[1])
        elif keyword == "DOMAIN_MIN":
            domain_min = tuple(float(value) for value in parts[1:4])
        elif keyword == "DOMAIN_MAX":
            domain_max = tuple(float(value) for value in parts[1:4])
        else:
            if len(parts) != 3:
                raise ValueError(f"Invalid CUBE row: {line}")
            row = tuple(float(value) for value in parts)
            if any(value < 0.0 or value > 1.0 for value in row):
                raise ValueError("CUBE output values must be in the range 0..1")
            rows.append(row)
    if size != 17:
        raise ValueError(f"Expected a Leica 17-cube, found size {size}")
    if len(rows) != size**3:
        raise ValueError(f"Expected {size**3} rows, found {len(rows)}")
    return CubeLUT(title, size, domain_min, domain_max, np.asarray(rows, dtype=np.float32))


def apply_cube_to_image(image_data: bytes, cube: CubeLUT, max_dimension: int = 1600) -> bytes:
    image = ImageOps.exif_transpose(Image.open(BytesIO(image_data))).convert("RGB")
    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    pixels = np.asarray(image, dtype=np.float32) / 255.0
    normalized = np.clip(
        (pixels - np.asarray(cube.domain_min))
        / (np.asarray(cube.domain_max) - np.asarray(cube.domain_min)),
        0.0,
        1.0,
    )
    scaled = normalized * (cube.size - 1)
    low = np.floor(scaled).astype(np.int16)
    high = np.minimum(low + 1, cube.size - 1)
    fraction = scaled - low

    def sample(red: np.ndarray, green: np.ndarray, blue: np.ndarray) -> np.ndarray:
        index = blue * cube.size * cube.size + green * cube.size + red
        return cube.values[index]

    r0, g0, b0 = low[..., 0], low[..., 1], low[..., 2]
    r1, g1, b1 = high[..., 0], high[..., 1], high[..., 2]
    fr, fg, fb = fraction[..., 0:1], fraction[..., 1:2], fraction[..., 2:3]
    c00 = sample(r0, g0, b0) * (1 - fr) + sample(r1, g0, b0) * fr
    c01 = sample(r0, g0, b1) * (1 - fr) + sample(r1, g0, b1) * fr
    c10 = sample(r0, g1, b0) * (1 - fr) + sample(r1, g1, b0) * fr
    c11 = sample(r0, g1, b1) * (1 - fr) + sample(r1, g1, b1) * fr
    c0 = c00 * (1 - fg) + c10 * fg
    c1 = c01 * (1 - fg) + c11 * fg
    output = c0 * (1 - fb) + c1 * fb
    rendered = Image.fromarray(np.uint8(np.clip(output, 0, 1) * 255), "RGB")
    buffer = BytesIO()
    rendered.save(buffer, format="JPEG", quality=94, optimize=True)
    return buffer.getvalue()