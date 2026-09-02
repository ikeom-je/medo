from datetime import date

from medo_core.artifacts import Artifact, ArtifactStore, GrownFrom, OptionMeta
from medo_core.knowledge import KnowledgeEntry, KnowledgeStore
from medo_core.facts import Fact, FactStore
from medo_core.nodes import Challenge
from medo_core.requirements import (
    FunctionalRequirement,
    RequirementsDoc,
    RequirementsStore,
)
from medo_core.status import project_status, stale_artifact_ids
from medo_core.storage import LocalJsonStorage

TODAY = date(2026, 7, 12)


def _doc(**kw) -> RequirementsDoc:
    base = dict(
        project="yoyaku",
        goal="飲食店の多言語対応AI自動音声予約システム",
        industry="飲食",
        challenges=[Challenge(text="外国語の電話予約に対応できず機会損失", confidence="confirmed")],
        functional=[FunctionalRequirement(text="ネット予約", confidence="confirmed")],
        open_questions=["ピーク時の同時電話着信数は?"],
    )
    base.update(kw)
    return RequirementsDoc(**base)


def _mini(**kw) -> Artifact:
    base = dict(
        project="yoyaku", type="mini-prfaq", requirements_version=1,
        generated_by="claude", content="# 候補セット",
        options=[OptionMeta(name="多言語AI音声予約")],
    )
    base.update(kw)
    return Artifact(**base)


def _prfaq(**kw) -> Artifact:
    base = dict(
        project="yoyaku",
        type="prfaq",
        requirements_version=1,
        grown_from=GrownFrom(artifact="mini-prfaq-v1", option="多言語AI音声予約"),
        generated_by="claude",
        content="# PRFAQ",
    )
    base.update(kw)
    return Artifact(**base)


def test_no_requirements_suggests_hearing(tmp_path):
    report = project_status(LocalJsonStorage(tmp_path), "yoyaku", tmp_path / "knowledge", today=TODAY)
    assert report["requirements"] is None and report["next_step"] == "hearing"


def test_requirements_only_suggests_propose_options(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    report = project_status(s, "yoyaku", tmp_path / "knowledge", today=TODAY)
    assert report["next_step"] == "propose-options"
    assert report["requirements"]["confidence_counts"]["confirmed"] == 2  # challenges+functional


def test_mini_prfaq_suggests_grow_prfaq(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    ArtifactStore(s).save("yoyaku", _mini())
    assert project_status(s, "yoyaku", tmp_path / "knowledge", today=TODAY)["next_step"] == "grow-prfaq"


def test_prfaq_reaches_up_to_date(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    ArtifactStore(s).save("yoyaku", _mini())
    ArtifactStore(s).save("yoyaku", _prfaq())
    assert project_status(s, "yoyaku", tmp_path / "knowledge", today=TODAY)["next_step"] == "up-to-date"


def test_stale_cited_fact_triggers_regenerate(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    FactStore(s).save("yoyaku", Fact(
        fact_id="fact-1", kind="market", statement="訪日客数", value=1.0,
        source="https://example.com/", retrieved="2025-01-01",
    ))
    ArtifactStore(s).save("yoyaku", _mini(cited_facts=["fact-1"]))
    assert project_status(s, "yoyaku", tmp_path / "knowledge", today=TODAY)["next_step"] == "regenerate-stale-artifacts"
    assert stale_artifact_ids(s, "yoyaku", tmp_path / "knowledge", today=TODAY) == ["mini-prfaq-v1"]


def test_stale_cited_knowledge_triggers_regenerate(tmp_path):
    s = LocalJsonStorage(tmp_path)
    k = tmp_path / "knowledge"
    RequirementsStore(s).save("yoyaku", _doc())
    KnowledgeStore(k).save(KnowledgeEntry(
        entry_id="tech-1", kind="tech", statement="x",
        source="https://cloud.google.com/", retrieved="2020-01-01", note=""
    ))
    ArtifactStore(s).save("yoyaku", _mini(cited_knowledge=["tech-1"]))
    assert project_status(s, "yoyaku", k, today=TODAY)["next_step"] == "regenerate-stale-artifacts"


def test_regeneration_recovers_via_latest_per_type(tmp_path):
    s = LocalJsonStorage(tmp_path)
    store = RequirementsStore(s)
    art = ArtifactStore(s)
    k = tmp_path / "knowledge"
    store.save("yoyaku", _doc())                       # 要件v1
    art.save("yoyaku", _mini())                        # mini-prfaq-v1
    store.save("yoyaku", _doc(goal="改"))              # 要件v2 → v1候補セットが陳腐化
    assert project_status(s, "yoyaku", k, today=TODAY)["next_step"] == "regenerate-stale-artifacts"
    art.save("yoyaku", _mini(requirements_version=2))  # 再生成
    assert project_status(s, "yoyaku", k, today=TODAY)["next_step"] == "grow-prfaq"
