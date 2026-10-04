from pathlib import Path
from unittest.mock import MagicMock

from medo_core.storage import FirestoreStorage, LocalJsonStorage


def test_local_put_get_roundtrip(tmp_path: Path):
    s = LocalJsonStorage(tmp_path)
    s.put("catalog/vertex-ai__context-caching", {"service": "vertex-ai"})
    assert s.get("catalog/vertex-ai__context-caching") == {"service": "vertex-ai"}


def test_local_get_missing_returns_none(tmp_path: Path):
    s = LocalJsonStorage(tmp_path)
    assert s.get("catalog/nothing") is None


def test_local_list_returns_document_paths(tmp_path: Path):
    s = LocalJsonStorage(tmp_path)
    s.put("catalog/a__x", {"v": 1})
    s.put("catalog/b__y", {"v": 2})
    s.put("projects/p1/requirements/v1", {"v": 3})
    assert sorted(s.list("catalog")) == ["catalog/a__x", "catalog/b__y"]
    assert s.list("projects/p1/requirements") == ["projects/p1/requirements/v1"]
    assert s.list("empty") == []


def test_firestore_storage_delegates_to_client():
    client = MagicMock()
    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = {"service": "vertex-ai"}
    client.document.return_value.get.return_value = snap
    doc_ref = MagicMock()
    doc_ref.id = "a__x"
    client.collection.return_value.list_documents.return_value = [doc_ref]

    s = FirestoreStorage(client)
    assert s.get("catalog/a__x") == {"service": "vertex-ai"}
    s.put("catalog/a__x", {"service": "v"})
    client.document.return_value.set.assert_called_once_with({"service": "v"})
    assert s.list("catalog") == ["catalog/a__x"]


def test_firestore_get_missing_returns_none():
    client = MagicMock()
    snap = MagicMock()
    snap.exists = False
    client.document.return_value.get.return_value = snap
    assert FirestoreStorage(client).get("catalog/none") is None


def test_list_children_returns_project_dirs_without_json(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    storage.put("projects/p1/facts/fact-1", {"x": 1})
    storage.put("projects/p2/requirements/v1", {"x": 1})

    assert storage.list("projects") == []
    assert storage.list_children("projects") == ["p1", "p2"]


def test_list_children_of_missing_prefix_is_empty(tmp_path):
    assert LocalJsonStorage(tmp_path).list_children("projects") == []


def test_list_children_returns_sorted_unique_file_and_directory_names(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    storage.put("projects/p2", {"x": 1})
    storage.put("projects/p1/facts/fact-1", {"x": 1})
    storage.put("projects/p1", {"x": 1})

    assert storage.list_children("projects") == ["p1", "p2"]


def test_firestore_list_children_includes_parents_without_document_bodies():
    client = MagicMock()
    client.collection.return_value.list_documents.return_value = [
        MagicMock(id="p2"), MagicMock(id="p1"),
    ]

    assert FirestoreStorage(client).list_children("projects") == ["p1", "p2"]
    client.collection.assert_called_once_with("projects")
