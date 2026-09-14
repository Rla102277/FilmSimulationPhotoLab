#!/usr/bin/env python3
"""Generate four red-fast 17-cube film-inspired Leica Q3 Looks."""

from pathlib import Path


ROOT = Path(__file__).parent / "q3_iphone_ia_four_film_looks"


def clamp(x: float) -> float:
    return min(max(x, 0.0), 1.0)


def luma(r: float, g: float, b: float) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def film_curve(x: float, contrast: float, lift: float, shoulder: float) -> float:
    y = (x - 0.5) * (1.0 + contrast) + 0.5 + lift
    y -= shoulder * pow(max(y, 0.0), 2.25) * 0.18
    return clamp(y)


def nostalgic(r: float, g: float, b: float) -> tuple[float, float, float]:
    y = luma(r, g, b)
    shadow_weight = pow(1.0 - y, 1.4)
    highlight_weight = pow(y, 1.7)
    sat = 0.94 + 0.16 * shadow_weight
    rr = y + (r - y) * sat
    gg = y + (g - y) * sat
    bb = y + (b - y) * sat
    rr += 0.050 * highlight_weight
    gg += 0.024 * highlight_weight
    bb -= 0.042 * highlight_weight
    return tuple(film_curve(v, -0.055, 0.012, 0.16) for v in (rr, gg, bb))


def acros(r: float, g: float, b: float) -> tuple[float, float, float]:
    # Slight green emphasis gives natural skin separation and detailed shadows.
    y = 0.20 * r + 0.74 * g + 0.06 * b
    y = film_curve(y, 0.09, 0.010, 0.12)
    y = clamp(y + 0.012 * pow(1.0 - y, 2.0))
    return y, y, y


def hp5(r: float, g: float, b: float) -> tuple[float, float, float]:
    y = 0.23 * r + 0.70 * g + 0.07 * b
    y = film_curve(y, 0.18, -0.006, 0.10)
    # Firmer toe than ACROS, with a restrained highlight shoulder.
    y = clamp(y - 0.018 * pow(1.0 - y, 2.2))
    return y, y, y


def edo(r: float, g: float, b: float) -> tuple[float, float, float]:
    y = luma(r, g, b)
    sat = 0.72
    rr = y + (r - y) * sat
    gg = y + (g - y) * sat
    bb = y + (b - y) * sat
    # Slight blue/cyan cast with muted warm colors and a faded C-41 toe.
    rr -= 0.022 + 0.012 * y
    gg += 0.009
    bb += 0.038 - 0.010 * y
    return tuple(film_curve(v, -0.12, 0.022, 0.10) for v in (rr, gg, bb))


LOOKS = [
    ("IA Nostalgic", "nostalgic", "Standard", nostalgic),
    ("IA Acros", "acros", "Standard", acros),
    ("IA HP5", "hp5", "Standard", hp5),
    ("IA Edo 400", "edo400", "Standard", edo),
]


for title, slug, base_style, transform in LOOKS:
    folder = ROOT / slug
    folder.mkdir(parents=True, exist_ok=True)
    lines = [
        "#Created by: Infinite Arch Leica Look Builder",
        "#Unique Leica Look ID: 27",
        f"#Based Filmstyle Mode: {base_style}",
        "",
        f'TITLE "{title}"',
        "",
        "LUT_3D_SIZE 17",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
        "",
    ]
    # Q3 empirical order: red changes fastest, then green, then blue.
    for blue_index in range(17):
        blue = blue_index / 16
        for green_index in range(17):
            green = green_index / 16
            for red_index in range(17):
                red = red_index / 16
                out = transform(red, green, blue)
                lines.append(" ".join(f"{clamp(value):.6f}" for value in out))
    cube = folder / f"{slug}.CUBE"
    cube.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(cube)
