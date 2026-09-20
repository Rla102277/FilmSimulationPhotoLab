"""Unit tests for DCP → Leica 17³ CUBE export."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from core.color.cube import parse_cube
from core.color.dcp_export import dcp_file_to_leica_cube, dcp_to_cube_lut

M9 = Path("/Users/randyarchambault/Downloads/InfiniteArchLeicaCLI/reference/M9_DCP")
SAMPLE = M9 / "M9 Digital Camera Fuji 400H L.dcp"
ARCHIVE = Path(__file__).resolve().parents[1] / "attached_assets" / "0_ALL_DCP_CUBE_LIBRARY_1789502493370.zip"


class DcpExportTests(unittest.TestCase):
    def test_m9_400h_becomes_valid_leica_17_cube(self) -> None:
        if not SAMPLE.is_file():
            self.skipTest("M9 DCP sample not on disk")
        cube_bytes = dcp_file_to_leica_cube(
            SAMPLE, look_id=1007, name="IA 400H", base=0
        )
        cube = parse_cube(cube_bytes)
        self.assertEqual(cube.size, 17)
        self.assertEqual(cube.values.shape, (4913, 3))
        text = cube_bytes.decode("ascii")
        self.assertIn("#Unique Leica Look ID: 1007", text)
        self.assertIn("#Based Filmstyle Mode: Standard", text)
        self.assertIn('TITLE "IA 400H"', text)
        axis = np.linspace(0.0, 1.0, 17)
        identity = np.asarray([(r, g, b) for b in axis for g in axis for r in axis])
        mean = float(np.linalg.norm(cube.values - identity, axis=1).mean())
        self.assertGreater(mean, 0.01)

    def test_two_stocks_differ(self) -> None:
        a = M9 / "M9 Digital Camera Fuji 400H L.dcp"
        b = M9 / "M9 Digital Camera Ultra 100 - L.dcp"
        if not a.is_file() or not b.is_file():
            self.skipTest("M9 DCP samples not on disk")
        ca = dcp_to_cube_lut(a.read_bytes(), filename=a.name)
        cb = dcp_to_cube_lut(b.read_bytes(), filename=b.name)
        self.assertGreater(float(np.max(np.abs(ca.values - cb.values))), 0.01)


if __name__ == "__main__":
    unittest.main()
