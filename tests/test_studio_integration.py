from __future__ import annotations

import unittest

from server.api.studio import _look_id, _normalize_ui_graph


class StudioIntegrationTests(unittest.TestCase):
    def test_frontend_source_filename_is_reported_as_unresolved(self) -> None:
        graph = {
            "name": "Unresolved UI Look", "version": "v1.2", "base": "Standard",
            "layers": [{"id": "lut", "name": "3D LUT", "type": "lut", "enabled": True,
                        "strength": 35, "source": "missing.CUBE"}],
            "controls": {},
        }
        normalized = _normalize_ui_graph(graph)
        unresolved = [node for node in normalized["nodes"] if node.get("unresolved_source")]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["unresolved_source"], "missing.CUBE")

    def test_frontend_layers_and_auto_id_are_normalized(self) -> None:
        graph = {
            "name": "Graph Name", "version": "v1.2", "base": "Standard",
            "layers": [
                {"id": "input-layer", "name": "Input", "type": "normalization",
                 "enabled": True, "strength": 100},
                {"id": "output-layer", "name": "Output", "type": "output",
                 "enabled": True, "strength": 100},
            ],
            "controls": {},
        }
        normalized = _normalize_ui_graph(graph)
        self.assertEqual(normalized["base"], 0)
        self.assertEqual(normalized["nodes"][0]["strength"], 1.0)
        self.assertIn("output", [node["type"] for node in normalized["nodes"]])
        self.assertEqual(_look_id("AUTO-1142"), 1142)
