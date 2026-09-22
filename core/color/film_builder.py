"""Free deterministic film-style LUT builder.

This is intentionally described as procedural generation, not cloud AI.
"""

from __future__ import annotations

import re

import numpy as np

from core.color.cube import CubeLUT, serialize_leica_cube


def infer_settings(text: str) -> dict:
    words = set(re.findall(r"[a-z]+", text.lower()))
    settings = {
        "exposure": 0.0,
        "contrast": 1.05,
        "saturation": 0.95,
        "warmth": 0.0,
        "fade": 0.0,
        "highlight_softness": 0.12,
        "monochrome": False,
    }
    if words & {"warm", "golden", "amber", "sunset", "nostalgic"}:
        settings["warmth"] += 0.055
    if words & {"cool", "cyan", "winter", "blue"}:
        settings["warmth"] -= 0.05
    if words & {"faded", "matte", "vintage", "lifted"}:
        settings["fade"] = 0.075
        settings["contrast"] -= 0.12
    if words & {"punchy", "dramatic", "contrasty", "crisp", "noir"}:
        settings["contrast"] += 0.22
    if words & {"soft", "gentle", "portrait", "pastel"}:
        settings["contrast"] -= 0.13
        settings["highlight_softness"] += 0.14
    if words & {"vivid", "rich", "colorful", "saturated"}:
        settings["saturation"] += 0.18
    if words & {"muted", "restrained", "desaturated", "subtle"}:
        settings["saturation"] -= 0.2
    if words & {"bright", "airy"}:
        settings["exposure"] += 0.06
    if words & {"dark", "moody", "dense"}:
        settings["exposure"] -= 0.05
    if words & {"monochrome", "black", "white", "bw", "noir"}:
        settings["monochrome"] = True
        settings["saturation"] = 0.0
    return settings


def normalize_settings(settings: dict) -> dict:
    bounds = {
        "exposure": (-0.2, 0.2),
        "contrast": (0.65, 1.45),
        "saturation": (0.0, 1.4),
        "warmth": (-0.12, 0.12),
        "fade": (0.0, 0.16),
        "highlight_softness": (0.0, 0.45),
    }
    normalized = {}
    for key, (minimum, maximum) in bounds.items():
        value = float(settings.get(key, infer_settings("")[key]))
        normalized[key] = max(minimum, min(maximum, value))
    normalized["monochrome"] = bool(settings.get("monochrome", False))
    if normalized["monochrome"]:
        normalized["saturation"] = 0.0
    return normalized


def build_film_cube(
    intent: str,
    profile_text: str = "",
    look_id: int = 1200,
    name: str = "Custom Film Look",
    settings: dict | None = None,
) -> tuple[bytes, dict]:
    settings = normalize_settings(settings or infer_settings(f"{intent} {profile_text[:20000]}"))
    axis = np.linspace(0.0, 1.0, 17, dtype=np.float32)
    rows = []
    for blue in axis:
        for green in axis:
            for red in axis:
                rgb = np.array([red, green, blue], dtype=np.float32)
                rgb = rgb + settings["exposure"]
                rgb = (rgb - 0.5) * settings["contrast"] + 0.5
                luminance = float(rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))
                rgb = luminance + (rgb - luminance) * settings["saturation"]
                rgb += np.array([settings["warmth"], settings["warmth"] * 0.2, -settings["warmth"]], dtype=np.float32)
                rgb = rgb * (1.0 - settings["fade"]) + settings["fade"]
                softness = settings["highlight_softness"]
                rgb = np.where(rgb > 0.72, 0.72 + (rgb - 0.72) / (1.0 + softness * 4.0), rgb)
                if settings["monochrome"]:
                    gray = float(rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32))
                    rgb[:] = gray
                rows.append(np.clip(rgb, 0.0, 1.0))
    cube = CubeLUT(name, 17, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), np.asarray(rows))
    return serialize_leica_cube(cube, look_id, name, 1 if settings["monochrome"] else 0), settings
