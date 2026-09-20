from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tempfile
import unittest
import zipfile

from server.api.leica_lab import PackInput, build_pack


class LeicaExportTests(unittest.TestCase):
    def test_pack_is_deterministic_and_every_payload_is_verified(self) -> None:
        first = build_pack(PackInput(look_ids=[1204, 1201]))
        second = build_pack(PackInput(look_ids=[1201, 1204]))
        self.assertEqual(first.body, second.body)
        self.assertEqual(hashlib.sha256(first.body).hexdigest(), first.headers["x-pack-sha256"])
        with zipfile.ZipFile(io.BytesIO(first.body)) as archive:
            names = archive.namelist()
            self.assertEqual(names[0], "manifest.json")
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual([look["id"] for look in manifest["looks"]], [1201, 1204])
            self.assertEqual([look["name"] for look in manifest["looks"]], ["Silver Grain", "Warm Negative"])
            self.assertTrue(all(look["compile_parse_verified"] for look in manifest["looks"]))
            self.assertEqual(len(names), 11)
            checksum_lines = archive.read("checksums.txt").decode().splitlines()
            self.assertEqual(len(checksum_lines), 10)

        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(io.BytesIO(first.body)) as archive:
                archive.extractall(directory)
            validation = subprocess.run(
                ["python", "injector.py", "--list"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
            self.assertIn("VALIDATION ONLY", validation.stdout)

    def test_pack_rejects_duplicate_looks(self) -> None:
        with self.assertRaisesRegex(Exception, "duplicate"):
            build_pack(PackInput(look_ids=[1204, 1204]))


if __name__ == "__main__":
    unittest.main()