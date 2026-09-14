#!/usr/bin/env python3
"""Generate an order-independent constant-magenta diagnostic 17-cube."""

from pathlib import Path


destination = Path(__file__).parent / "q3_iphone_ia_magenta_proof" / "IAMagentaProof.CUBE"
lines = [
    "#Created by: Infinite Arch Leica Look Builder",
    "#Unique Leica Look ID: 27",
    "#Based Filmstyle Mode: Standard",
    "",
    'TITLE "IA Magenta Proof"',
    "",
    "LUT_3D_SIZE 17",
    "DOMAIN_MIN 0.0 0.0 0.0",
    "DOMAIN_MAX 1.0 1.0 1.0",
    "",
]

# Every possible input maps to the same legal RGB triplet. The result cannot be
# neutralized by red-fast versus blue-fast CUBE row ordering.
lines.extend(["1.000000 0.000000 1.000000"] * (17 ** 3))
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text("\n".join(lines) + "\n", encoding="ascii")
print(destination)
