from __future__ import annotations

import tempfile
import unittest

from server.db.studio_repository import StudioRepository


class StudioPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = StudioRepository(url=f"sqlite:///{self.directory.name}/studio.sqlite3")
        self.graph = {
            "name": "Durable Look", "version": "draft", "look_id": 1142,
            "base": "Standard", "layers": [], "controls": {"contrast": 8},
        }

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_save_appends_versions_and_preserves_master_graph(self) -> None:
        created = self.repository.save_look({
            "name": "Durable Look", "graph": self.graph, "status": "experiment",
            "tags": ["chrome", "travel"], "notes": "First pass", "rating": 4,
            "favorite": True,
        })
        changed = {**self.graph, "controls": {"contrast": 20}}
        updated = self.repository.save_look({
            "id": created["id"], "name": "Durable Look", "graph": changed,
            "status": "published", "tags": ["chrome"], "notes": "Approved",
            "rating": 5, "favorite": True,
        })

        self.assertEqual(updated["version"], "v1.2")
        self.assertEqual([item["label"] for item in updated["versions"]], ["v1.2", "v1.1"])
        self.assertEqual(updated["graph"]["controls"]["contrast"], 20)
        self.assertEqual(updated["versions"][1]["graph"]["controls"]["contrast"], 8)
        self.assertEqual(updated["status"], "published")
        self.assertEqual(updated["tags"], ["chrome"])
        self.assertTrue(updated["favorite"])

    def test_graph_name_is_used_when_metadata_name_is_omitted(self) -> None:
        created = self.repository.save_look({"graph": self.graph})
        self.assertEqual(created["name"], "Durable Look")

    def test_stale_workspace_write_cannot_replace_newer_state(self) -> None:
        latest = {"graph": {**self.graph, "name": "Latest"}, "revision": 1,
                  "client_id": "tab-a", "client_sequence": 2}
        stale = {"graph": {**self.graph, "name": "Stale"}, "revision": 1,
                 "client_id": "tab-b", "client_sequence": 1}
        self.repository.save_workspace(latest, expected_revision=0)
        with self.assertRaises(Exception):
            self.repository.save_workspace(stale, expected_revision=0)
        self.assertEqual(self.repository.get_workspace()["state"]["graph"]["name"], "Latest")

    def test_later_same_tab_write_wins_after_ambiguous_response(self) -> None:
        first = {"graph": self.graph, "revision": 1, "client_id": "tab-a", "client_sequence": 1}
        latest = {"graph": {**self.graph, "name": "Latest"}, "revision": 1,
                  "client_id": "tab-a", "client_sequence": 2}
        self.repository.save_workspace(first, expected_revision=0)
        saved = self.repository.save_workspace(latest, expected_revision=0)
        self.assertEqual(saved["state"]["revision"], 2)
        self.assertEqual(self.repository.get_workspace()["state"]["graph"]["name"], "Latest")

    def test_snapshots_and_workspace_survive_new_repository_instance(self) -> None:
        look = self.repository.save_look({"name": "Durable Look", "graph": self.graph})
        snapshot = self.repository.add_snapshot(look["id"], "Before curve", self.graph)
        state = {
            "graph": self.graph, "history": [{**self.graph, "name": "Previous"}],
            "future": [], "snapshots": [snapshot], "lookId": look["id"],
        }
        state["revision"] = 1
        self.repository.save_workspace(state, expected_revision=0)

        reopened = StudioRepository(url=f"sqlite:///{self.directory.name}/studio.sqlite3")
        self.assertEqual(reopened.get_workspace()["state"]["history"][0]["name"], "Previous")
        self.assertEqual(reopened.get_look(look["id"])["snapshots"][0]["name"], "Before curve")


if __name__ == "__main__":
    unittest.main()

def test_versions_and_workspace_are_private(tmp_path):
    import pytest
    repo = StudioRepository(url=f'sqlite:///{tmp_path}/private.sqlite3')
    graph = {'name': 'Private', 'nodes': []}
    look = repo.save_look({'graph': graph}, owner_id='alice')
    assert repo.list_looks(owner_id='bob') == []
    with pytest.raises(KeyError):
        repo.get_look(look['id'], owner_id='bob')
    with pytest.raises(KeyError):
        repo.save_look({'id': look['id'], 'graph': graph}, owner_id='bob')
    with pytest.raises(KeyError):
        repo.add_snapshot(look['id'], 'Other', graph, owner_id='bob')
    repo.save_workspace({'graph': graph}, 0, owner_id='alice')
    assert repo.get_workspace(owner_id='bob') is None
