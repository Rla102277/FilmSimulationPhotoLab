from __future__ import annotations

import unittest

from verify_bundle import validate


class AuthoritativeV12Tests(unittest.TestCase):
    def test_archive_and_manifest_assets(self) -> None:
        manifest = validate()
        self.assertEqual([item["id"] for item in manifest], list(range(1001, 1010)))
        self.assertEqual(manifest[0]["name"], "IA Invitation")
        self.assertEqual(manifest[-1]["name"], "IA Ember")


if __name__ == "__main__":
    unittest.main()

