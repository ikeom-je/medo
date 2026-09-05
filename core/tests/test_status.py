from datetime import date

from medo_core.artifacts import Artifact, ArtifactStore, GrownFrom, OptionMeta
from medo_core.knowledge import KnowledgeEntry, KnowledgeStore
from medo_core.facts import Fact, FactStore
from medo_core.nodes import AsIs, Challenge, Stakeholder
from medo_core.requirements import (
    FunctionalRequirement,
    RequirementsDoc,
    RequirementsStore,
)
from medo_core.status import project_status, stale_artifact_ids
from medo_core.storage import LocalJsonStorage
from medo_core.workflow import WorkflowRecorder

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


def _project(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    WorkflowRecorder(storage).save_requirements("p1", RequirementsDoc(
        project="p1",
        as_is=[AsIs(text="実態", visibility="internal")],
        stakeholders=[Stakeholder(text="部長", is_decision_maker=True)],
    ), today=TODAY)
    return storage


def _codes(status: dict) -> list[str]:
    return [a["code"] for a in status["actions"]]


def test_no_requirements_suggests_hearing(tmp_path):
    report = project_status(LocalJsonStorage(tmp_path), "yoyaku", tmp_path / "knowledge", today=TODAY)
    assert report["requirements"] is None and report["next_step"] == "hearing"


def test_requirements_only_suggests_propose_options(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    report = project_status(s, "yoyaku", tmp_path / "knowledge", today=TODAY)
    assert report["next_step"] == "propose-options"
    assert report["requirements"]["confidence_counts"]["confirmed"] == 2  # challenges+functional


def test_outdated_coverage_suggests_grow_prfaq_instead_of_regeneration(tmp_path):
    s = LocalJsonStorage(tmp_path)
    RequirementsStore(s).save("yoyaku", _doc())
    ArtifactStore(s).save("yoyaku", _mini())
    report = project_status(s, "yoyaku", tmp_path / "knowledge", today=TODAY)

    assert {
        "next_step": report["next_step"],
        "stale": report["artifacts"][0]["stale"],
        "regeneration_action": "regenerate_stale_artifacts" in _codes(report),
    } == {
        "next_step": "grow-prfaq",
        "stale": False,
        "regeneration_action": False,
    }


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


def test_fermi_does_not_become_stale_when_requirements_sections_change(tmp_path):
    s = LocalJsonStorage(tmp_path)
    store = RequirementsStore(s)
    store.save("yoyaku", _doc())
    ArtifactStore(s).save("yoyaku", Artifact(
        project="yoyaku", type="fermi", requirements_version=1, content="{}",
    ))
    saved = store.get("yoyaku")
    assert saved is not None
    store.save("yoyaku", saved.model_copy(update={"goal": "予約業務を完全自動化する"}))

    report = project_status(s, "yoyaku", tmp_path / "knowledge", today=TODAY)

    assert (
        [(row["id"], row["stale"]) for row in report["artifacts"]],
        stale_artifact_ids(s, "yoyaku", tmp_path / "knowledge", today=TODAY),
    ) == ([
        ("fermi-v1", False),
    ], [])


def test_id_only_migration_does_not_mark_artifact_stale(tmp_path):
    s = LocalJsonStorage(tmp_path)
    s.put("projects/yoyaku/requirements/v1", {
        "project": "yoyaku",
        "version": 1,
        "as_is": [{"text": "電話予約を手作業で受けている", "visibility": "internal"}],
    })
    ArtifactStore(s).save("yoyaku", Artifact(
        project="yoyaku", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))
    store = RequirementsStore(s)
    doc = store.get("yoyaku")
    assert doc is not None
    store.save("yoyaku", doc, today=TODAY)

    report = project_status(s, "yoyaku", tmp_path / "knowledge", today=TODAY)

    assert report["artifacts"][0]["stale"] is False


def test_regenerating_latest_artifact_recovers_from_dependent_section_change(tmp_path):
    s = LocalJsonStorage(tmp_path)
    store = RequirementsStore(s)
    art = ArtifactStore(s)
    k = tmp_path / "knowledge"
    store.save("yoyaku", _doc())
    art.save("yoyaku", _mini(covered_challenge_ids=["ch-1"]))
    saved = store.get("yoyaku")
    assert saved is not None
    changed = saved.challenges[0].model_copy(update={"text": "予約の取りこぼしが常態化"})
    store.save("yoyaku", saved.model_copy(update={"challenges": [changed]}))

    assert project_status(s, "yoyaku", k, today=TODAY)["next_step"] == "regenerate-stale-artifacts"
    art.save("yoyaku", _mini(requirements_version=2, covered_challenge_ids=["ch-1"]))

    report = project_status(s, "yoyaku", k, today=TODAY)

    assert report["next_step"] == "grow-prfaq"
    assert "regenerate_stale_artifacts" not in _codes(report)
    assert report["artifacts"] == [{
        "id": "mini-prfaq-v2",
        "type": "mini-prfaq",
        "requirements_version": 2,
        "stale": False,
    }]


def test_status_returns_four_branches_in_full_view(tmp_path):
    storage = _project(tmp_path)

    status = project_status(storage, "p1", tmp_path, view="full")

    assert set(status) >= {"model", "workflow", "readiness", "actions", "diagnostic_phase"}


def test_summary_view_puts_actions_first(tmp_path):
    """Skillが最初に読むものを「足りない」ではなく「次にできること」にする。"""
    storage = _project(tmp_path)

    status = project_status(storage, "p1", tmp_path)

    assert list(status)[0] == "actions"


def test_summary_view_omits_failed_conditions(tmp_path):
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert "failed_conditions" not in status["readiness"]


def test_branch_view_returns_only_that_branch(tmp_path):
    status = project_status(_project(tmp_path), "p1", tmp_path, view="model")

    assert set(status) == {"project", "diagnostic_phase", "model"}


def test_missing_project_still_returns_phase1_shape(tmp_path):
    """既存CLIの挙動を壊さない。"""
    status = project_status(LocalJsonStorage(tmp_path), "unknown", tmp_path)

    assert status["next_step"] == "hearing"


def test_discovery_phase_still_returns_actions(tmp_path):
    """readiness を出さない段階でも、次に何をすべきかは示す。"""
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert "draft_strawman_to_be" in _codes(status)


def test_unanswered_milestone_is_the_top_action(tmp_path):
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert _codes(status)[0] == "answer_tobe_checkpoint"


def test_next_step_keeps_phase1_vocabulary(tmp_path):
    """フェーズ1のSkillは next_step を完全一致で分岐している。"""
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert status["next_step"] in {
        "hearing", "propose-options", "grow-prfaq",
        "regenerate-stale-artifacts", "up-to-date",
    }


def test_summary_view_keeps_phase1_compatibility_fields(tmp_path):
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert set(status) >= {"requirements", "facts", "artifacts", "next_step"}


def test_run_check_is_not_offered_without_its_target(tmp_path):
    """討議用スライドが無い状態で expression_safety を求めても実行できない。"""
    codes_with_refs = [
        a for a in project_status(_project(tmp_path), "p1", tmp_path)["actions"]
        if a["code"] == "run_check"
    ]

    assert all("expression_safety" not in a.get("refs", []) for a in codes_with_refs)
