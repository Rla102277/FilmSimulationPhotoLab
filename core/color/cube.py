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
    if size is None or not 2 <= size <= 256:
        raise ValueError(f"Invalid or missing LUT_3D_SIZE: {size}")
    if len(rows) != size**3:
        raise ValueError(f"Expected {size**3} rows, found {len(rows)}")
    return CubeLUT(title, size, domain_min, domain_max, np.asarray(rows, dtype=np.float32))


def resample_cube(cube: CubeLUT, target_size: int = 17) -> CubeLUT:
    if not 2 <= target_size <= 256:
        raise ValueError("Target CUBE size must be between 2 and 256")
    if cube.size == target_size:
        return cube
    axis = np.linspace(0, cube.size - 1, target_size, dtype=np.float32)
    output = []

    def sample(red: float, green: float, blue: float) -> np.ndarray:
        low = np.floor([red, green, blue]).astype(int)
        high = np.minimum(low + 1, cube.size - 1)
        fr, fg, fb = np.asarray([red, green, blue]) - low

        def value(r: int, g: int, b: int) -> np.ndarray:
            return cube.values[b * cube.size * cube.size + g * cube.size + r]

        c00 = value(low[0], low[1], low[2]) * (1 - fr) + value(high[0], low[1], low[2]) * fr
        c01 = value(low[0], low[1], high[2]) * (1 - fr) + value(high[0], low[1], high[2]) * fr
        c10 = value(low[0], high[1], low[2]) * (1 - fr) + value(high[0], high[1], low[2]) * fr
        c11 = value(low[0], high[1], high[2]) * (1 - fr) + value(high[0], high[1], high[2]) * fr
        return (c00 * (1 - fg) + c10 * fg) * (1 - fb) + (c01 * (1 - fg) + c11 * fg) * fb

    for blue in axis:
        for green in axis:
            for red in axis:
                output.append(sample(float(red), float(green), float(blue)))
    return CubeLUT(cube.title, target_size, cube.domain_min, cube.domain_max, np.asarray(output, dtype=np.float32))


def serialize_leica_cube(cube: CubeLUT, look_id: int, name: str, base: int) -> bytes:
    normalized = resample_cube(cube, 17)
    values = normalized.values
    if base == 1:
        luminance = (
            values[:, 0:1] * 0.2126
            + values[:, 1:2] * 0.7152
            + values[:, 2:3] * 0.0722
        )
        values = np.repeat(luminance, 3, axis=1)
    mode = "Monochrome" if base == 1 else "Standard"
    lines = [
        f"#Unique Leica Look ID: {look_id}",
        f"#Based Filmstyle Mode: {mode}",
        f'TITLE "{name}"',
        "LUT_3D_SIZE 17",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    lines.extend(" ".join(f"{float(value):.6f}" for value in row) for row in values)
    return ("\n".join(lines) + "\n").encode("ascii")


def parse_hald(data: bytes) -> CubeLUT:
    image = Image.open(BytesIO(data)).convert("RGB")
    if image.width != image.height:
        raise ValueError("Hald CLUT must be a square image")
    cube_size = round((image.width * image.height) ** (1 / 3))
    if cube_size**3 != image.width * image.height:
        raise ValueError("Image dimensions do not form a complete Hald color cube")
    values = np.asarray(image, dtype=np.float32).reshape(-1, 3) / 255.0
    return CubeLUT("Imported Hald CLUT", cube_size, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), values)


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