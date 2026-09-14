#!/usr/bin/env python3
"""Generate the deliberately obvious 17-cube used by the Q3 custom-LUT test."""

from pathlib import Path


destination = Path(__file__).parent / "q3_iphone_infinite_arch_test" / "InfiniteArchTest.CUBE"
lines = [
    "#Created by: Infinite Arch Leica Look Builder",
    "#Unique Leica Look ID: 27",
    "#Based Filmstyle Mode: Standard",
    "",
    'TITLE "Infinite Arch Test"',
    "",
    "LUT_3D_SIZE 17",
    "DOMAIN_MIN 0.0 0.0 0.0",
    "DOMAIN_MAX 1.0 1.0 1.0",
    "",
]

# Leica's captured CUBEs enumerate blue fastest, then green, then red.
# Swap red and blue and compress green toward the midpoint. The transform is
# valid and bounded, but unmistakable in a photograph: blue skies become red,
# warm skin becomes blue, while green remains recognizable but muted.
for red_index in range(17):
    red = red_index / 16
    for green_index in range(17):
        green = green_index / 16
        for blue_index in range(17):
            blue = blue_index / 16
            out_red = blue
            out_green = 0.15 + 0.70 * green
            out_blue = red
            lines.append(f"{out_red:.6f} {out_green:.6f} {out_blue:.6f}")

destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text("\n".join(lines) + "\n", encoding="ascii")
print(destination)
