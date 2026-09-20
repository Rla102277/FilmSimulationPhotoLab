#!/usr/bin/env python3
"""CLI: DCP → Leica 17³ CUBE.

Example:
  python scripts/dcp_to_leica_cube.py path/to/profile.dcp -o out.CUBE --look-id 1200 --name "My Look"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.color.cube import parse_cube
from core.color.dcp_export import dcp_file_to_leica_cube


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert a DCP creative profile into a Leica 17³ CUBE")
    ap.add_argument("dcp", type=Path, help="Input .dcp file")
    ap.add_argument("-o", "--output", type=Path, required=True, help="Output .CUBE path")
    ap.add_argument("--look-id", type=int, default=1200)
    ap.add_argument("--name", default=None, help="Look title (default: DCP ProfileName)")
    ap.add_argument("--base", type=int, choices=(0, 1), default=0, help="0=Standard, 1=Monochrome")
    ap.add_argument("--strength", type=float, default=1.0)
    ap.add_argument("--tone-curve", action="store_true", help="Also bake ProfileToneCurve")
    args = ap.parse_args()

    if not args.dcp.is_file():
        raise SystemExit(f"missing DCP: {args.dcp}")

    cube_bytes = dcp_file_to_leica_cube(
        args.dcp,
        look_id=args.look_id,
        name=args.name,
        base=args.base,
        strength=args.strength,
        include_tone_curve=args.tone_curve,
    )
    args.output.write_bytes(cube_bytes)
    parsed = parse_cube(cube_bytes)
    print(
        f"Wrote {args.output} — LUT_3D_SIZE {parsed.size}, "
        f"{parsed.values.shape[0]} rows, title={parsed.title!r}"
    )


if __name__ == "__main__":
    main()
