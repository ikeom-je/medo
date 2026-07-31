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
        cited_knowledge=["vertex-ai__context-caching"],
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


def test_mini_prfaq_holds_option_set_metadata(store: ArtifactStore):
    from medo_core.artifacts import OptionMeta

    artifact = _artifact(
        type="mini-prfaq",
        options=[
            OptionMeta(name="多言語AI音声予約", approach_type="業務改革"),
            OptionMeta(name="予約代行アウトソース", approach_type="既存解決"),
        ],
        cited_facts=["fact-1"],
    )
    assert store.save("yoyaku", artifact) == "mini-prfaq-v1"
    got = store.get("yoyaku", "mini-prfaq-v1")
    assert [o.name for o in got.options] == [
        "多言語AI音声予約",
        "予約代行アウトソース",
    ]
    assert got.cited_facts == ["fact-1"]


def test_prfaq_requires_grown_from(store: ArtifactStore):
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _artifact(type="prfaq")

    from medo_core.artifacts import GrownFrom

    artifact = _artifact(
        type="prfaq",
        grown_from=GrownFrom(artifact="mini-prfaq-v1", option="多言語AI音声予約"),
    )
    assert store.save("yoyaku", artifact) == "prfaq-v1"


def test_fermi_artifact_requires_generated_by_none(store: ArtifactStore):
    artifact = _artifact(type="fermi", generated_by=None)
    assert store.save("yoyaku", artifact) == "fermi-v1"

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _artifact(type="fermi", generated_by="claude")


def test_generative_artifact_requires_generated_by(store: ArtifactStore):
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _artifact(type="architecture", generated_by=None)
