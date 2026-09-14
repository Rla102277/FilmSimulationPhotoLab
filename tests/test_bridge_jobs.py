from __future__ import annotations

import unittest

from server.services.bridge_jobs import create_job, transition_job


class BridgeJobTests(unittest.TestCase):
    def test_read_only_job_uses_explicit_state_machine(self) -> None:
        job = create_job("LEICA_READ_LOOKS", {"target_camera": "LEICA_Q3_FAMILY"})
        self.assertEqual(job["status"], "QUEUED")
        cancelled = transition_job(job["id"], "CANCELLED")
        self.assertEqual(cancelled["status"], "CANCELLED")

    def test_write_job_rejects_non_authoritative_checksum(self) -> None:
        with self.assertRaisesRegex(ValueError, "checksum"):
            create_job(
                "LEICA_INSTALL_LOOK",
                {
                    "look_id": 1004,
                    "look_name": "IA Presence",
                    "artifact_sha256": "not-authoritative",
                    "target_camera": "LEICA_Q3_43",
                },
            )

    def test_invalid_state_transition_is_rejected(self) -> None:
        job = create_job("LEICA_READ_LOOKS", {"target_camera": "LEICA_Q3_FAMILY"})
        with self.assertRaisesRegex(ValueError, "Invalid job transition"):
            transition_job(job["id"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()