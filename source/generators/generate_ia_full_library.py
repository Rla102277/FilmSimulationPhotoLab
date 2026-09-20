#!/usr/bin/env python3
"""Generate all Infinite Arch Q3 CUBEs and strict 180x90 1-bit BMP icons."""

from __future__ import annotations

import struct
from pathlib import Path


ROOT = Path(__file__).parent / "ia_full_library" / "assets"
SIZE = 17


def clamp(x: float) -> float:
    return min(max(x, 0.0), 1.0)


def lum(r: float, g: float, b: float) -> float:
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ia_tone(x: float, contrast: float, highlights: float, shadows: float) -> float:
    y = (x - 0.5) * (1.0 + contrast) + 0.5
    y += highlights * pow(max(y, 0.0), 2.4) * 0.22
    y += shadows * pow(max(1.0 - y, 0.0), 2.4) * 0.22
    return clamp(y)


def named_recipe(
    *, monochrome: bool = False, contrast: float = 0.0, saturation: float = 0.0,
    warmth: float = 0.0, highlights: float = 0.0, shadows: float = 0.0
):
    def apply(r: float, g: float, b: float) -> tuple[float, float, float]:
        if monochrome:
            y = lum(r, g, b)
            values = (y, y, y)
        else:
            y = lum(r, g, b)
            sat = 1.0 + saturation
            values = (
                y + (r - y) * sat + warmth * 0.08,
                y + (g - y) * sat,
                y + (b - y) * sat - warmth * 0.08,
            )
        return tuple(ia_tone(v, contrast, highlights, shadows) for v in values)
    return apply


def film_curve(x: float, contrast: float, lift: float, shoulder: float) -> float:
    y = (x - 0.5) * (1.0 + contrast) + 0.5 + lift
    y -= shoulder * pow(max(y, 0.0), 2.25) * 0.18
    return clamp(y)


def nostalgic(r: float, g: float, b: float) -> tuple[float, float, float]:
    y = lum(r, g, b)
    shadow_weight = pow(1.0 - y, 1.4)
    highlight_weight = pow(y, 1.7)
    sat = 0.94 + 0.16 * shadow_weight
    values = [y + (v - y) * sat for v in (r, g, b)]
    values[0] += 0.050 * highlight_weight
    values[1] += 0.024 * highlight_weight
    values[2] -= 0.042 * highlight_weight
    return tuple(film_curve(v, -0.055, 0.012, 0.16) for v in values)


def acros(r: float, g: float, b: float) -> tuple[float, float, float]:
    y = 0.20 * r + 0.74 * g + 0.06 * b
    y = film_curve(y, 0.09, 0.010, 0.12)
    y = clamp(y + 0.012 * pow(1.0 - y, 2.0))
    return y, y, y


def hp5(r: float, g: float, b: float) -> tuple[float, float, float]:
    y = 0.23 * r + 0.70 * g + 0.07 * b
    y = film_curve(y, 0.18, -0.006, 0.10)
    y = clamp(y - 0.018 * pow(1.0 - y, 2.2))
    return y, y, y


def edo(r: float, g: float, b: float) -> tuple[float, float, float]:
    y = lum(r, g, b)
    values = [y + (v - y) * 0.72 for v in (r, g, b)]
    values[0] -= 0.022 + 0.012 * y
    values[1] += 0.009
    values[2] += 0.038 - 0.010 * y
    return tuple(film_curve(v, -0.12, 0.022, 0.10) for v in values)


LOOKS = [
    ("Invitation", "invitation", True, named_recipe(monochrome=True, contrast=-0.08, highlights=-0.08, shadows=-0.05)),
    ("Witness", "witness", True, named_recipe(monochrome=True, contrast=0.16, highlights=0.06, shadows=0.12)),
    ("Memory", "memory", True, named_recipe(monochrome=True, contrast=-0.12, warmth=0.02, highlights=-0.14, shadows=-0.08)),
    ("Truth", "truth", False, named_recipe(contrast=-0.06, saturation=-0.05, highlights=-0.08, shadows=-0.05)),
    ("Presence", "presence", False, named_recipe(contrast=-0.08, saturation=-0.10, warmth=0.04, highlights=-0.14, shadows=-0.05)),
    ("Threshold", "threshold", False, named_recipe(contrast=0.05, saturation=0.12, warmth=0.02, highlights=-0.03, shadows=0.05)),
    ("Stillness", "stillness", False, named_recipe(contrast=-0.04, saturation=0.10, warmth=0.03, highlights=-0.14)),
    ("IA Nostalgic", "nostalgic", False, nostalgic),
    ("IA Acros", "acros", True, acros),
    ("IA HP5", "hp5", True, hp5),
    ("IA Edo 400", "edo400", False, edo),
]


FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    " ": ["00000"] * 7,
}


def draw_text(canvas: list[list[int]], text: str, y: int, scale: int) -> None:
    char_width = 5 * scale
    gap = scale
    total = len(text) * char_width + max(0, len(text) - 1) * gap
    start_x = (180 - total) // 2
    for index, char in enumerate(text.upper()):
        glyph = FONT[char]
        origin_x = start_x + index * (char_width + gap)
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    for sy in range(scale):
                        for sx in range(scale):
                            canvas[y + gy * scale + sy][origin_x + gx * scale + sx] = 1


def make_bmp(label: str) -> bytes:
    width, height = 180, 90
    canvas = [[0] * width for _ in range(height)]
    draw_text(canvas, "IA", 12, 4)
    draw_text(canvas, label, 55, 2)
    stride = ((width + 31) // 32) * 4
    pixels = bytearray(stride * height)
    for y in range(height):
        row_offset = (height - 1 - y) * stride
        for x, value in enumerate(canvas[y]):
            if value:
                pixels[row_offset + x // 8] |= 1 << (7 - (x % 8))
    image_size = len(pixels) + 2
    file_size = 62 + image_size
    header = (
        b"BM"
        + struct.pack("<IHHI", file_size, 0, 0, 62)
        + struct.pack("<IiiHHIIiiII", 40, width, height, 1, 1, 0, image_size, 11811, 11811, 0, 0)
        + b"\x00\x00\x00\x00\xff\xff\xff\x00"
    )
    return header + bytes(pixels) + b"\x00\x00"


generated_icons = []
for title, slug, monochrome, transform in LOOKS:
    folder = ROOT / slug
    folder.mkdir(parents=True, exist_ok=True)
    lines = [
        "#Created by: Infinite Arch Leica Look Builder",
        "#Unique Leica Look ID: 0",
        "#Based Filmstyle Mode: Standard",
        "",
        f'TITLE "{title}"',
        "",
        "LUT_3D_SIZE 17",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
        "",
    ]
    for blue_index in range(SIZE):
        blue = blue_index / (SIZE - 1)
        for green_index in range(SIZE):
            green = green_index / (SIZE - 1)
            for red_index in range(SIZE):
                red = red_index / (SIZE - 1)
                values = transform(red, green, blue)
                lines.append(" ".join(f"{clamp(v):.6f}" for v in values))
    (folder / "look.CUBE").write_text("\n".join(lines) + "\n", encoding="ascii")
    icon_label = title[3:] if title.startswith("IA ") else title
    icon = make_bmp(icon_label)
    (folder / "look.bmp").write_bytes(icon)
    generated_icons.append((title, icon))
    (folder / "mode.txt").write_text("mono\n" if monochrome else "color\n")
    print(title, folder)


def decode_bmp_pixels(data: bytes) -> list[list[int]]:
    offset = struct.unpack_from("<I", data, 10)[0]
    width, height = struct.unpack_from("<ii", data, 18)
    stride = ((width + 31) // 32) * 4
    output = [[0] * width for _ in range(height)]
    for y in range(height):
        row_offset = offset + (height - 1 - y) * stride
        for x in range(width):
            output[y][x] = 255 if data[row_offset + x // 8] & (1 << (7 - x % 8)) else 0
    return output


cols, rows, gap = 3, 4, 10
sheet_width = cols * 180 + (cols + 1) * gap
sheet_height = rows * 90 + (rows + 1) * gap
sheet = [bytearray([96] * sheet_width) for _ in range(sheet_height)]
for index, (_title, icon) in enumerate(generated_icons):
    origin_x = gap + (index % cols) * (180 + gap)
    origin_y = gap + (index // cols) * (90 + gap)
    pixels = decode_bmp_pixels(icon)
    for y, row in enumerate(pixels):
        sheet[origin_y + y][origin_x : origin_x + 180] = bytes(row)
contact = ROOT.parent / "icon_contact.pgm"
contact.write_bytes(
    f"P5\n{sheet_width} {sheet_height}\n255\n".encode("ascii") + b"".join(sheet)
)
print("icon contact", contact)
