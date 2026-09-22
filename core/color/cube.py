from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import math

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
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        keyword = parts[0].upper()
        if keyword == "TITLE":
            title = line.partition(" ")[2].strip().strip('"')
        elif keyword == "LUT_3D_SIZE":
            if size is not None or len(parts) != 2:
                raise ValueError("Expected one LUT_3D_SIZE declaration")
            size = int(parts[1])
        elif keyword == "DOMAIN_MIN":
            if len(parts) != 4:
                raise ValueError("DOMAIN_MIN requires three values")
            domain_min = tuple(float(value) for value in parts[1:4])
        elif keyword == "DOMAIN_MAX":
            if len(parts) != 4:
                raise ValueError("DOMAIN_MAX requires three values")
            domain_max = tuple(float(value) for value in parts[1:4])
        else:
            if len(parts) != 3:
                raise ValueError(f"Invalid CUBE row: {line}")
            row = tuple(float(value) for value in parts)
            if any(not math.isfinite(value) or abs(value) > 1e37 for value in row):
                raise ValueError("CUBE output values must be finite and within ±1e37")
            rows.append(row)
    if size is None or not 2 <= size <= 256:
        raise ValueError(f"Invalid or missing LUT_3D_SIZE: {size}")
    if not all(math.isfinite(low) and math.isfinite(high) and high > low
               for low, high in zip(domain_min, domain_max)):
        raise ValueError("CUBE domains must be finite and DOMAIN_MAX must exceed DOMAIN_MIN")
    if len(rows) != size**3:
        raise ValueError(f"Expected {size**3} rows, found {len(rows)}")
    return CubeLUT(title, size, domain_min, domain_max, np.asarray(rows, dtype=np.float32))


def sample_cube(pixels: np.ndarray, cube: CubeLUT) -> np.ndarray:
    """Sample in the source domain; use wide indices for 33/65/256 grids."""
    normalized = np.clip((pixels - np.asarray(cube.domain_min)) /
                         (np.asarray(cube.domain_max) - np.asarray(cube.domain_min)), 0, 1)
    scaled = normalized * (cube.size - 1)
    low = np.floor(scaled).astype(np.int64)
    high = np.minimum(low + 1, cube.size - 1)
    fraction = scaled - low
    output = np.zeros_like(pixels, dtype=np.float64)
    for blue in (0, 1):
        for green in (0, 1):
            for red in (0, 1):
                bits = np.array([red, green, blue])
                indices = np.where(bits, high, low)
                weights = np.prod(np.where(bits, fraction, 1 - fraction), axis=-1)
                offset = indices[..., 0] + cube.size * indices[..., 1] + cube.size**2 * indices[..., 2]
                output += cube.values[offset] * weights[..., None]
    return output


def resample_cube(cube: CubeLUT, target_size: int = 17) -> CubeLUT:
    """Bake the source transform onto a unit-domain grid for Leica/display RGB."""
    if not 2 <= target_size <= 256:
        raise ValueError("Target CUBE size must be between 2 and 256")
    if cube.size == target_size and cube.domain_min == (0., 0., 0.) and cube.domain_max == (1., 1., 1.):
        return cube
    axis = np.linspace(0, 1, target_size, dtype=np.float32)
    points = np.asarray([(r, g, b) for b in axis for g in axis for r in axis], dtype=np.float32)
    return CubeLUT(cube.title, target_size, (0., 0., 0.), (1., 1., 1.),
                   sample_cube(points, cube).astype(np.float32))


def serialize_leica_cube(cube: CubeLUT, look_id: int, name: str, base: int) -> bytes:
    if base not in (0, 1):
        raise ValueError("Leica base must be Standard (0) or Monochrome (1)")
    if any(char in name for char in (chr(34), "\n", "\r", "\0")):
        raise ValueError("Look name cannot contain quotes or control characters")
    normalized = resample_cube(cube, 17)
    values = normalized.values
    if base == 1:
        luminance = (
            values[:, 0:1] * 0.2126
            + values[:, 1:2] * 0.7152
            + values[:, 2:3] * 0.0722
        )
        values = np.repeat(luminance, 3, axis=1)
    # Camera output is bounded; general-purpose floating-point CUBEs are not.
    values = np.clip(values, 0.0, 1.0)
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
    output = sample_cube(pixels, cube)
    rendered = Image.fromarray(np.uint8(np.clip(output, 0, 1) * 255), "RGB")
    buffer = BytesIO()
    rendered.save(buffer, format="JPEG", quality=94, optimize=True)
    return buffer.getvalue()
