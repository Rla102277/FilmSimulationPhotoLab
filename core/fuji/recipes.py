"""Fuji recipe validation without inventing body capabilities or recipe values."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROFILE_FILES = {
    "FUJI_X_E5": ROOT / "camera_profiles" / "fuji_xe5.json",
    "FUJI_GFX50R": ROOT / "camera_profiles" / "fuji_gfx50r.json",
}
RECIPE_CONTROLS = {
    "film_simulation",
    "dynamic_range",
    "highlight",
    "shadow",
    "color",
    "sharpness",
    "noise_reduction",
    "clarity",
    "grain",
    "color_chrome_effect",
    "color_chrome_fx_blue",
    "white_balance_mode",
    "wb_red_shift",
    "wb_blue_shift",
}


def load_camera_profiles() -> list[dict]:
    profiles = []
    for profile_id, path in PROFILE_FILES.items():
        profile = json.loads(path.read_text())
        profile["id"] = profile_id
        profiles.append(profile)
    return profiles


def validate_recipe(camera_profile_id: str, settings: dict) -> dict:
    profiles = {profile["id"]: profile for profile in load_camera_profiles()}
    if camera_profile_id not in profiles:
        raise ValueError("Unsupported Fuji camera profile")
    unknown = sorted(set(settings) - RECIPE_CONTROLS)
    if unknown:
        raise ValueError(f"Unknown Fuji recipe controls: {', '.join(unknown)}")
    profile = profiles[camera_profile_id]
    return {
        "camera_profile": profile,
        "settings": settings,
        "verification_status": "unverified" if not profile["capabilities_verified"] else "profile_verified",
        "warning": (
            "Recipe values are stored as experimental intent. Camera capabilities "
            "have not been verified and are not inferred."
        ),
    }
