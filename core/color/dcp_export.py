"""Direct DCP → Leica 17³ CUBE conversion.

Uses the HueSat / Look table creative path (not camera ColorMatrix calibration).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from core.assets.inspect import inspect_source_asset
from core.color.cube import CubeLUT, serialize_leica_cube
from core.color.source_transforms import dcp_transform


def dcp_to_cube_lut(
    dcp_bytes: bytes,
    *,
    filename: str = "profile.dcp",
    strength: float = 1.0,
    illuminant_mix: float = 0.5,
    mode: str = "bounded_display",
    include_tone_curve: bool = False,
) -> CubeLUT:
    """Bake a DCP's creative tables into a 17³ CubeLUT in display RGB."""
    inspection = inspect_source_asset(filename, dcp_bytes)
    tags = inspection["metadata"].get("tags") or {}
    if not any(k in tags for k in ("ProfileHueSatMapData1", "ProfileLookTableData")):
        raise ValueError(
            "DCP has no HueSat/Look tables; calibration-only profiles cannot define a creative Look"
        )
    name = tags.get("ProfileName") or Path(filename).stem
    axis = np.linspace(0.0, 1.0, 17, dtype=np.float32)
    identity = np.asarray(
        [(r, g, b) for b in axis for g in axis for r in axis],
        dtype=np.float32,
    )
    node = {
        "tags": tags,
        "mode": mode,
        "illuminant_mix": illuminant_mix,
    }
    transformed = dcp_transform(identity, node)
    if strength != 1.0:
        transformed = identity + (transformed - identity) * float(strength)
    transformed = np.clip(transformed, 0.0, 1.0).astype(np.float32)

    if include_tone_curve and "ProfileToneCurve" in tags:
        curve = tags["ProfileToneCurve"]
        if isinstance(curve, list) and len(curve) >= 4 and len(curve) % 2 == 0:
            xs = np.asarray(curve[0::2], dtype=np.float64)
            ys = np.asarray(curve[1::2], dtype=np.float64)
            for channel in range(3):
                transformed[:, channel] = np.interp(transformed[:, channel], xs, ys).astype(np.float32)
            transformed = np.clip(transformed, 0.0, 1.0)

    return CubeLUT(str(name), 17, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), transformed)


def dcp_to_leica_cube(
    dcp_bytes: bytes,
    *,
    look_id: int = 1200,
    name: str | None = None,
    base: int = 0,
    filename: str = "profile.dcp",
    strength: float = 1.0,
    include_tone_curve: bool = False,
) -> bytes:
    """Return Leica-headed 17³ CUBE bytes ready for payload packaging."""
    cube = dcp_to_cube_lut(
        dcp_bytes,
        filename=filename,
        strength=strength,
        include_tone_curve=include_tone_curve,
    )
    title = name or cube.title
    return serialize_leica_cube(cube, look_id, title, base)


def dcp_file_to_leica_cube(
    path: str | Path,
    *,
    look_id: int = 1200,
    name: str | None = None,
    base: int = 0,
    strength: float = 1.0,
    include_tone_curve: bool = False,
) -> bytes:
    path = Path(path)
    return dcp_to_leica_cube(
        path.read_bytes(),
        look_id=look_id,
        name=name,
        base=base,
        filename=path.name,
        strength=strength,
        include_tone_curve=include_tone_curve,
    )
