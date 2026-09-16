from __future__ import annotations

import tempfile
import unittest

import numpy as np

from core.assets.inspect import inspect_source_asset
from core.assets.library import SourceLibrary
from core.color.cube import parse_cube
from core.color.graph_compiler import compile_graph_cube
from server.api.studio import _normalize_ui_graph


def graph(*nodes: dict) -> dict:
    return {"version": 1, "nodes": [{"id": "input", "type": "input"}, *nodes,
                                      {"id": "output", "type": "output"}]}


def cube_text(transform: str = "identity") -> str:
    rows = []
    for blue in np.linspace(0, 1, 2):
        for green in np.linspace(0, 1, 2):
            for red in np.linspace(0, 1, 2):
                value = (1 - red, green, blue) if transform == "invert-red" else (red, green, blue)
                rows.append(" ".join(str(float(channel)) for channel in value))
    return "LUT_3D_SIZE 2\n" + "\n".join(rows) + "\n"


class NextPhaseGraphTests(unittest.TestCase):
    def test_adobe_iirc_dcp_container_extracts_components(self) -> None:
        import zipfile
        from core.assets.profile_catalog import DEFAULT_ARCHIVE, catalog

        with zipfile.ZipFile(DEFAULT_ARCHIVE) as bundle:
            member = next(name for name in bundle.namelist() if name.lower().endswith(".dcp"))
            inspection = inspect_source_asset(member, bundle.read(member))
        component_ids = {item["id"] for item in inspection["components"]}
        self.assertIn("ColorMatrix1", component_ids)
        self.assertIn("ProfileToneCurve", component_ids)
        names = [item["display_name"] for item in catalog()]
        self.assertIn("Agfa Scala 200", names)
        self.assertFalse(any("Digital Camera" in name or "LEICA M" in name or "Variant" in name
                             for name in names))

    def test_source_sha256_dedupe_retains_components(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = SourceLibrary(f"{directory}/library.sqlite3")
            first = library.add("identity.CUBE", cube_text().encode(), "text/plain", "camera test")
            second = library.add("renamed.CUBE", cube_text().encode(), "text/plain", "second upload")
            self.assertFalse(first["duplicate"])
            self.assertTrue(second["duplicate"])
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(library.get(first["id"])["components"][0]["type"], "cube_lut")
            self.assertEqual(len(library.list(search="identity")), 1)
            self.assertEqual(len(library.list(asset_type="CUBE")), 1)

    def test_frontend_graph_normalizes_layers_controls_and_does_not_mutate(self) -> None:
        frontend = {
            "name": "Frontend Look", "version": "v1.2", "base": "Monochrome",
            "layers": [
                {"id": "a", "name": "Input Normalization", "type": "normalization",
                 "enabled": True, "strength": 100},
                {"id": "b", "name": "Creative LUT", "type": "lut",
                 "enabled": False, "strength": 35,
                 "cube": cube_text("invert-red")},
                {"id": "c", "name": "Output Normalize", "type": "output",
                 "enabled": True, "strength": 100},
            ],
            "controls": {"exposure": 25, "contrast": 8, "highlights": -12},
        }
        normalized = _normalize_ui_graph(frontend)
        self.assertEqual(frontend["base"], "Monochrome")
        self.assertEqual(normalized["base"], 1)
        self.assertEqual([node["id"] for node in normalized["nodes"][:4]],
                         ["input", "a", "b", "c"])
        self.assertAlmostEqual(normalized["nodes"][2]["strength"], 0.35)
        controls = {node["id"]: node for node in normalized["nodes"]}
        self.assertAlmostEqual(controls["control-exposure"]["params"]["value"], 0.25)

    def test_source_layer_reference_is_preserved_for_hydration(self) -> None:
        normalized = _normalize_ui_graph({
            "layers": [{"id": "component", "type": "lut", "strength": 200,
                        "enabled": True, "source_id": "source-1", "component_id": "cube"}],
            "controls": {},
        })
        layer = next(node for node in normalized["nodes"] if node["id"] == "component")
        self.assertEqual(layer["source_id"], "source-1")
        self.assertEqual(layer["component_id"], "cube")
        self.assertNotIn("unresolved_source", layer)
        self.assertEqual(layer["strength"], 2.0)

    def test_order_changes_compiled_cube(self) -> None:
        curve = {"id": "curve", "type": "curve",
                 "points": [[0, 0], [0.5, 0.2], [1, 1]]}
        matrix = {"id": "matrix", "type": "matrix",
                  "matrix": [[1.2, 0, 0], [0, 0.7, 0], [0, 0, 1]]}
        first, _ = compile_graph_cube(graph(curve, matrix), size=2)
        second, _ = compile_graph_cube(graph(matrix, curve), size=2)
        self.assertNotEqual(first, second)

    def test_enable_strength_and_valid_17_cube(self) -> None:
        lut = {"id": "lut", "type": "lut", "cube": cube_text("invert-red"), "strength": 0.5}
        cube_data, report = compile_graph_cube(graph(lut))
        parsed = parse_cube(cube_data)
        self.assertEqual(parsed.size, 17)
        self.assertEqual(parsed.values.shape, (17 ** 3, 3))
        self.assertTrue(report["valid"])
        self.assertAlmostEqual(float(parsed.values[0, 0]), 0.5, places=5)
        disabled, _ = compile_graph_cube(graph({**lut, "enabled": False}))
        self.assertNotEqual(cube_data, disabled)
