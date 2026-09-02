from pathlib import Path

import pytest
from pydantic import ValidationError

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.storage import LocalJsonStorage


@pytest.fixture
def store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(LocalJsonStorage(tmp_path))


def _legacy_artifact(**kw) -> Artifact:
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
    assert store.save("yoyaku", _legacy_artifact()) == "architecture-v1"
    assert store.save("yoyaku", _legacy_artifact()) == "architecture-v2"
    assert store.save("yoyaku", _legacy_artifact(type="comparison")) == "comparison-v1"


def test_get_and_list(store: ArtifactStore):
    store.save("yoyaku", _legacy_artifact())
    got = store.get("yoyaku", "architecture-v1")
    assert got is not None and got.generated_by == "claude"
    assert store.get("yoyaku", "architecture-v9") is None
    assert len(store.list("yoyaku")) == 1
    assert store.list("nashi") == []


def test_stale_artifacts(store: ArtifactStore):
    store.save("yoyaku", _legacy_artifact(requirements_version=1))
    store.save("yoyaku", _legacy_artifact(requirements_version=2, type="comparison"))
    stale = store.stale_artifacts("yoyaku", current_requirements_version=2)
    assert [a.type for a in stale] == ["architecture"]


def test_mini_prfaq_holds_option_set_metadata(store: ArtifactStore):
    from medo_core.artifacts import OptionMeta

    artifact = _legacy_artifact(
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
        _legacy_artifact(type="prfaq")

    from medo_core.artifacts import GrownFrom, OptionMeta

    store.save(
        "yoyaku",
        _legacy_artifact(
            type="mini-prfaq",
            options=[OptionMeta(name="多言語AI音声予約")],
        ),
    )
    artifact = _legacy_artifact(
        type="prfaq",
        grown_from=GrownFrom(artifact="mini-prfaq-v1", option="多言語AI音声予約"),
    )
    assert store.save("yoyaku", artifact) == "prfaq-v1"


def test_fermi_artifact_requires_generated_by_none(store: ArtifactStore):
    artifact = _legacy_artifact(type="fermi", generated_by=None)
    assert store.save("yoyaku", artifact) == "fermi-v1"

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _legacy_artifact(type="fermi", generated_by="claude")


def test_generative_artifact_requires_generated_by(store: ArtifactStore):
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _legacy_artifact(type="architecture", generated_by=None)


def _artifact(**kw) -> Artifact:
    base = {
        "project": "p1",
        "type": "as-is-report",
        "requirements_version": 1,
        "generated_by": "claude",
        "content": "# 現状",
    }
    base.update(kw)
    return Artifact.model_validate(base)


def test_slides_require_slide_kind():
    """親typeからの推論に頼ると、複数の親を持てる設計では判別が曖昧になる。"""
    with pytest.raises(ValidationError):
        _artifact(type="slides", content="---\nmarp: true")


def test_slides_accept_discussion_kind():
    a = _artifact(type="slides", slide_kind="discussion", derived_from=["as-is-report-v1"])

    assert a.slide_kind == "discussion"


def test_non_slides_reject_slide_kind():
    with pytest.raises(ValidationError):
        _artifact(type="research", slide_kind="discussion")


def test_rejected_option_records_why_it_was_dropped():
    """却下案の見送り理由が失われると、意思決定者の納得感が大きく変わる。"""
    from medo_core.artifacts import RejectedOption

    a = _artifact(type="comparison",
                  rejected_options=[RejectedOption(name="B案", reason="運用負荷が高い",
                                                   accepted_risk="初期費用が上がる")])

    assert a.rejected_options[0].accepted_risk == "初期費用が上がる"


def test_rejected_options_are_not_allowed_on_reporting_types():
    with pytest.raises(ValidationError):
        _artifact(type="as-is-report",
                  rejected_options=[{"name": "B案", "reason": "運用負荷"}])


def test_generated_by_accepts_codex():
    """どのホストからでも生成できる設計であり、来歴が追える必要がある。"""
    assert _artifact(generated_by="codex").generated_by == "codex"


def test_save_rejects_parent_of_disallowed_type(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(type="research", generated_by="claude", content="調査"))

    with pytest.raises(ValueError, match="derived_from"):
        store.save("p1", _artifact(type="slides", slide_kind="discussion",
                                   derived_from=["research-v1"]))


def test_save_rejects_missing_parent(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))

    with pytest.raises(ValueError, match="as-is-report-v9"):
        store.save("p1", _artifact(type="slides", slide_kind="discussion",
                                   derived_from=["as-is-report-v9"]))


def test_save_rejects_discussion_slides_without_exactly_one_parent(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))

    with pytest.raises(ValueError, match="ちょうど1"):
        store.save("p1", _artifact(type="slides", slide_kind="discussion"))


def test_save_rejects_as_is_report_with_multiple_research_parents(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(type="research", content="調査1"))
    store.save("p1", _artifact(type="research", content="調査2"))

    with pytest.raises(ValueError, match="0または1件"):
        store.save("p1", _artifact(derived_from=["research-v1", "research-v2"]))


def test_save_rejects_grown_from_option_absent_from_candidate_set(tmp_path):
    from medo_core.artifacts import GrownFrom, OptionMeta

    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(type="mini-prfaq", options=[OptionMeta(name="A案")],
                               content="候補"))

    with pytest.raises(ValueError, match="B案"):
        store.save("p1", _artifact(type="prfaq",
                                   grown_from=GrownFrom(artifact="mini-prfaq-v1",
                                                        option="B案"),
                                   content="育成"))


def test_save_rejects_older_requirements_version_than_latest_of_same_type(tmp_path):
    """祖先判定は requirements_version の単調性で行うため、逆行を拒否する。"""
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(requirements_version=3))

    with pytest.raises(ValueError, match="requirements_version"):
        store.save("p1", _artifact(requirements_version=2))


def test_save_rejects_cyclic_dependency(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(type="research", content="調査"))
    store.save("p1", _artifact(type="as-is-report", derived_from=["research-v1"]))
    storage = store._storage
    raw = storage.get("projects/p1/artifacts/research-v1")
    raw["derived_from"] = ["as-is-report-v1"]
    storage.put("projects/p1/artifacts/research-v1", raw)

    with pytest.raises(ValueError, match="循環"):
        store.save("p1", _artifact(type="slides", slide_kind="discussion",
                                   derived_from=["as-is-report-v1"]))
