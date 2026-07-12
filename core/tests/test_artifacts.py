from pathlib import Path

import pytest
from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.storage import LocalJsonStorage


@pytest.fixture
def store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(LocalJsonStorage(tmp_path))


def _artifact(**kw) -> Artifact:
    base = dict(
        project="yoyaku",
        type="architecture",
        requirements_version=1,
        cited_catalog_entries=["vertex-ai__context-caching"],
        generated_by="claude",
        content="# アーキ案A\n...",
    )
    base.update(kw)
    return Artifact(**base)


def test_save_assigns_version_per_type(store: ArtifactStore):
    assert store.save("yoyaku", _artifact()) == "architecture-v1"
    assert store.save("yoyaku", _artifact()) == "architecture-v2"
    assert store.save("yoyaku", _artifact(type="slides")) == "slides-v1"


def test_get_and_list(store: ArtifactStore):
    store.save("yoyaku", _artifact())
    got = store.get("yoyaku", "architecture-v1")
    assert got is not None and got.generated_by == "claude"
    assert store.get("yoyaku", "architecture-v9") is None
    assert len(store.list("yoyaku")) == 1
    assert store.list("nashi") == []


def test_stale_artifacts(store: ArtifactStore):
    store.save("yoyaku", _artifact(requirements_version=1))
    store.save("yoyaku", _artifact(requirements_version=2, type="slides"))
    stale = store.stale_artifacts("yoyaku", current_requirements_version=2)
    assert [a.type for a in stale] == ["architecture"]
