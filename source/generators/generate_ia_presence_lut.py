#!/usr/bin/env python3
"""Generate Infinite Arch Presence in the Q3's empirically proven red-fast order."""

from pathlib import Path


def clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def tone(value: float, contrast: float, highlights: float, shadows: float) -> float:
    result = (value - 0.5) * (1.0 + contrast) + 0.5
    result += highlights * pow(max(result, 0.0), 2.4) * 0.22
    result += shadows * pow(max(1.0 - result, 0.0), 2.4) * 0.22
    return clamp(result)


destination = Path(__file__).parent / "q3_iphone_ia_presence" / "Presence.CUBE"
lines = [
    "#Created by: Infinite Arch Leica Look Builder",
    "#Unique Leica Look ID: 27",
    "#Based Filmstyle Mode: Standard",
    "",
    'TITLE "Presence"',
    "",
    "LUT_3D_SIZE 17",
    "DOMAIN_MIN 0.0 0.0 0.0",
    "DOMAIN_MAX 1.0 1.0 1.0",
    "",
]

contrast = -0.08
saturation = -0.10
warmth = 0.04
highlights = -0.14
shadows = -0.05

# Q3 empirical order: red changes fastest, then green, then blue.
for blue_index in range(17):
    blue = blue_index / 16
    for green_index in range(17):
        green = green_index / 16
        for red_index in range(17):
            red = red_index / 16
            luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            sat = 1.0 + saturation
            out_red = luminance + (red - luminance) * sat + warmth * 0.08
            out_green = luminance + (green - luminance) * sat
            out_blue = luminance + (blue - luminance) * sat - warmth * 0.08
            out_red = tone(out_red, contrast, highlights, shadows)
            out_green = tone(out_green, contrast, highlights, shadows)
            out_blue = tone(out_blue, contrast, highlights, shadows)
            lines.append(f"{out_red:.6f} {out_green:.6f} {out_blue:.6f}")

destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text("\n".join(lines) + "\n", encoding="ascii")
print(destination)
