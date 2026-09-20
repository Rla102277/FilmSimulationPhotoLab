from __future__ import annotations

import hashlib
import unittest

from core.color.cube import parse_cube
from core.leica.authoritative import (
    EXPECTED_SHA256,
    archive_inventory,
    get_authoritative_look,
    read_look_asset,
    verify_authoritative_archive,
)
from core.leica.payload import build_authoritative_payload, inspect_payload
from core.leica.compiler import compile_look_payload
from core.leica.parser import parse_look_payload
from core.leica.validator import verify_compiled_payload


class PhotoLabCoreTests(unittest.TestCase):
    def test_authoritative_archive_and_inventory_are_stable(self) -> None:
        verification = verify_authoritative_archive()
        self.assertTrue(verification["ok"])
        self.assertEqual(verification["actual_sha256"], EXPECTED_SHA256)
        inventory = archive_inventory()
        self.assertEqual(len(inventory), 42)
        self.assertEqual(
            sum(item["classification"] == "authoritative_cube" for item in inventory),
            9,
        )
        self.assertEqual(
            sum(item["classification"] == "authoritative_icon" for item in inventory),
            9,
        )

    def test_every_authoritative_cube_parses_as_red_fast_17_cube(self) -> None:
        for look_id in range(1001, 1010):
            look = get_authoritative_look(look_id)
            cube_data = read_look_asset(look_id, "cube")
            self.assertEqual(hashlib.sha256(cube_data).hexdigest(), look["cube_sha256"])
            cube = parse_cube(cube_data)
            self.assertEqual(cube.size, 17)
            self.assertEqual(cube.values.shape, (4913, 3))
            self.assertGreaterEqual(float(cube.values.min()), 0.0)
            self.assertLessEqual(float(cube.values.max()), 1.0)

    def test_payload_builder_round_trips_all_six_fields(self) -> None:
        payload = build_authoritative_payload(1004)
        decoded = inspect_payload(payload)
        self.assertEqual(decoded["field_count"], 6)
        self.assertEqual(decoded["look_id"], 1004)
        self.assertEqual(decoded["name"], "IA Presence")
        self.assertEqual(decoded["type"], 2)
        self.assertEqual(decoded["base"], 0)
        self.assertEqual(
            [field["name"] for field in decoded["fields"]],
            ["look_id", "name", "icon", "cube", "type", "base"],
        )

    def test_controlled_edit_compiles_parses_and_verifies(self) -> None:
        cube = read_look_asset(1004, "cube")
        icon = read_look_asset(1004, "icon")
        payload, report = compile_look_payload(
            1104,
            "IA Presence Edit",
            icon,
            cube,
            d864=2,
            base=0,
        )
        parsed = parse_look_payload(payload, include_binary=True)
        self.assertEqual(parsed["look_id"], 1104)
        self.assertEqual(parsed["name"], "IA Presence Edit")
        self.assertEqual(parsed["cube"], cube)
        self.assertEqual(parsed["icon"], icon)
        self.assertTrue(all(report["verification"].values()))
        self.assertTrue(
            verify_compiled_payload(
                payload,
                {
                    "look_id": 1104,
                    "name": "IA Presence Edit",
                    "icon": icon,
                    "cube": cube,
                    "d864": 2,
                    "base": 0,
                },
            )["valid"]
        )

    def test_compiler_rejects_unproven_property_values(self) -> None:
        cube = read_look_asset(1004, "cube")
        icon = read_look_asset(1004, "icon")
        with self.assertRaisesRegex(ValueError, "D864"):
            compile_look_payload(1104, "Invalid Type", icon, cube, d864=3, base=0)
        with self.assertRaisesRegex(ValueError, "D866"):
            compile_look_payload(1104, "Invalid Base", icon, cube, d864=2, base=7)


if __name__ == "__main__":
    unittest.main()