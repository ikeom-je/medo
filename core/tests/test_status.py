from datetime import date

from medo_core.artifacts import Artifact, ArtifactStore, GrownFrom, OptionMeta
from medo_core.checks import CHECK_REGISTRY
from medo_core.events import (
    ArtifactTarget,
    AsIsReportReviewed,
    CheckRecorded,
    RequirementsTarget,
    StakeholderResponded,
)
from medo_core.knowledge import KnowledgeEntry, KnowledgeStore
from medo_core.facts import Fact, FactStore
from medo_core.nodes import AsIs, Challenge, Gap, Stakeholder, ToBe
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


def _project_with_both_slide_kinds(tmp_path, stale_discussion=False):
    storage = _project(tmp_path)
    artifacts = ArtifactStore(storage)
    report = artifacts.save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))
    cited_facts = []
    if stale_discussion:
        FactStore(storage).save("p1", Fact(
            fact_id="fact-1", kind="market", statement="旧い根拠", value=1.0,
            source="https://example.com/", retrieved="2020-01-01",
        ))
        cited_facts = ["fact-1"]
    artifacts.save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=1,
        derived_from=[report], cited_facts=cited_facts,
        generated_by="claude", content="# 討議",
    ))
    mini = artifacts.save("p1", Artifact(
        project="p1", type="mini-prfaq", requirements_version=1,
        generated_by="claude", content="# 候補セット",
        options=[OptionMeta(name="A案")],
    ))
    prfaq = artifacts.save("p1", Artifact(
        project="p1", type="prfaq", requirements_version=1,
        grown_from=GrownFrom(artifact=mini, option="A案"),
        generated_by="claude", content="# PRFAQ",
    ))
    artifacts.save("p1", Artifact(
        project="p1", type="slides", slide_kind="final", requirements_version=1,
        derived_from=[prfaq], generated_by="claude", content="# 最終提案",
    ))
    return storage


def _save_final_slides(storage):
    return ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="slides", slide_kind="final", requirements_version=2,
        derived_from=["prfaq-v1"], generated_by="claude", content="# 最終提案",
    ))


def _phase_project(tmp_path, *, prfaq=False, final=False, signoff=False):
    storage = LocalJsonStorage(tmp_path)
    requirements = RequirementsStore(storage)
    requirements.save("p1", RequirementsDoc(
        project="p1",
        as_is=[AsIs(text="手作業で転記している", visibility="internal", confidence="confirmed")],
        to_be=[ToBe(text="転記を自動化する", confidence="confirmed")],
        stakeholders=[Stakeholder(
            text="部長", confidence="confirmed", is_decision_maker=True,
        )],
    ), today=TODAY)
    doc = requirements.get("p1")
    assert doc is not None
    requirements.save("p1", doc.model_copy(update={"gaps": [Gap(
        text="手作業から自動化への乖離", kind="goal", confidence="confirmed",
        from_as_is=[doc.as_is[0].id], from_to_be=[doc.to_be[0].id],
    )]}), today=TODAY)

    artifacts = ArtifactStore(storage)
    research = artifacts.save("p1", Artifact(
        project="p1", type="research", requirements_version=2,
        generated_by="claude", content="# 調査",
    ))
    report = artifacts.save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=2,
        generated_by="claude", content="# 現状",
    ))
    discussion = artifacts.save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=2,
        derived_from=[report], generated_by="claude", content="# 討議",
    ))

    recorder = WorkflowRecorder(storage)
    artifact_targets = {
        "source_quality": research,
        "as_is_articulation": report,
        "expression_safety": discussion,
    }
    for check, spec in CHECK_REGISTRY.items():
        target = (
            ArtifactTarget(artifact_id=artifact_targets[check])
            if spec.binding == "artifact_bound"
            else RequirementsTarget(version=2)
        )
        recorder.record("p1", CheckRecorded(
            target=target, occurred_on="2026-07-12", requirements_version=2,
            round_id=0, check=check, result="completed",
        ))
    recorder.record("p1", StakeholderResponded(
        target=RequirementsTarget(version=2), occurred_on="2026-07-12",
        requirements_version=2, round_id=0, stakeholder_id="sh-1",
        purpose="to_be_go_ahead", reaction="agreed",
    ))

    if prfaq:
        mini = artifacts.save("p1", Artifact(
            project="p1", type="mini-prfaq", requirements_version=2,
            generated_by="claude", content="# 候補セット",
            options=[OptionMeta(name="A案")],
        ))
        cited_facts = []
        if prfaq == "stale":
            FactStore(storage).save("p1", Fact(
                fact_id="fact-1", kind="market", statement="旧い根拠", value=1.0,
                source="https://example.com/", retrieved="2020-01-01",
            ))
            cited_facts = ["fact-1"]
        artifacts.save("p1", Artifact(
            project="p1", type="prfaq", requirements_version=2,
            grown_from=GrownFrom(artifact=mini, option="A案"), cited_facts=cited_facts,
            generated_by="claude", content="# PRFAQ",
        ))

    final_id = _save_final_slides(storage) if final else None
    if signoff:
        assert final_id is not None
        recorder.record("p1", StakeholderResponded(
            target=ArtifactTarget(artifact_id=final_id), occurred_on="2026-07-12",
            requirements_version=2, round_id=0, stakeholder_id="sh-1",
            purpose="phase_signoff", reaction="agreed",
        ))
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


def test_review_is_not_approved_before_anyone_reviews(tmp_path):
    """レビュー未実施でも open_findings は空。空を承認の証拠にできない。"""
    status = project_status(_project(tmp_path), "p1", tmp_path, view="workflow")

    assert status["workflow"]["review"]["approved"] is False


def test_review_is_approved_after_an_approved_review_of_the_current_target(tmp_path):
    storage = _project(tmp_path)
    report = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))
    slides = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=1,
        derived_from=[report], generated_by="claude", content="# 討議",
    ))
    WorkflowRecorder(storage).record("p1", AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report), occurred_on="2026-07-12",
        requirements_version=1, round_id=0, outcome="approved",
        reviewed_slides_id=slides,
    ))

    status = project_status(storage, "p1", tmp_path, view="workflow")

    assert status["workflow"]["review"]["approved"] is True


def test_review_is_not_approved_after_changes_requested_for_the_current_target(tmp_path):
    storage = _project(tmp_path)
    report = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))
    slides = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=1,
        derived_from=[report], generated_by="claude", content="# 討議",
    ))
    recorder = WorkflowRecorder(storage)
    recorder.record("p1", AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report), occurred_on="2026-07-12",
        requirements_version=1, round_id=0, outcome="approved",
        reviewed_slides_id=slides,
    ))
    recorder.record("p1", AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report), occurred_on="2026-07-13",
        requirements_version=1, round_id=0, outcome="changes_requested",
        reviewed_slides_id=slides, slide_findings=["根拠の表現を見直す"],
    ))

    status = project_status(storage, "p1", tmp_path, view="workflow")

    assert status["workflow"]["review"]["approved"] is False


def test_review_approval_does_not_carry_over_to_a_regenerated_report(tmp_path):
    """再生成した版は別物。前の版の承認を引き継ぐと未検証の資料を顧客に出す。"""
    storage = _project(tmp_path)
    report = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))
    slides = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=1,
        derived_from=[report], generated_by="claude", content="# 討議",
    ))
    WorkflowRecorder(storage).record("p1", AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report), occurred_on="2026-07-12",
        requirements_version=1, round_id=0, outcome="approved",
        reviewed_slides_id=slides,
    ))
    ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状(改訂)",
    ))

    status = project_status(storage, "p1", tmp_path, view="workflow")

    assert (status["workflow"]["review"]["current_target"],
            status["workflow"]["review"]["approved"]) == ("as-is-report-v2", False)


def test_summary_view_puts_actions_first(tmp_path):
    """Skillが最初に読むものを「足りない」ではなく「次にできること」にする。"""
    storage = _project(tmp_path)

    status = project_status(storage, "p1", tmp_path)

    assert list(status)[0] == "actions"


def test_summary_view_omits_failed_conditions(tmp_path):
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert "failed_conditions" not in status["readiness"]


def test_summary_view_omits_the_phase_judgement(tmp_path):
    """summaryは従来どおり標準周回のstateだけを返す。"""
    status = project_status(_phase_project(tmp_path, prfaq=True), "p1", tmp_path)

    assert set(status["readiness"]) == {"state"}


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


def test_compat_artifact_list_stays_keyed_by_type(tmp_path):
    """フェーズ1のSkillは artifacts 配列を型で引いている(status契約 §5)。"""
    storage = _project_with_both_slide_kinds(tmp_path)

    status = project_status(storage, "p1", tmp_path)

    assert len([row for row in status["artifacts"] if row["type"] == "slides"]) == 1


def test_stale_action_sees_both_slide_kinds(tmp_path):
    """type別に畳むと、staleな討議用スライドが最終提案の陰に隠れる。"""
    storage = _project_with_both_slide_kinds(tmp_path, stale_discussion=True)

    actions = project_status(storage, "p1", tmp_path)["actions"]
    regenerate = [a for a in actions if a["code"] == "regenerate_stale_artifacts"]

    assert regenerate and "slides-v1" in regenerate[0]["refs"]


def test_run_check_is_not_offered_without_its_target(tmp_path):
    """討議用スライドが無い状態で expression_safety を求めても実行できない。"""
    codes_with_refs = [
        a for a in project_status(_project(tmp_path), "p1", tmp_path)["actions"]
        if a["code"] == "run_check"
    ]

    assert all("expression_safety" not in a.get("refs", []) for a in codes_with_refs)


def test_readiness_view_carries_the_phase_judgement(tmp_path):
    """フェーズ完了の可否は収束の次の問いであり、別viewを呼ばせない。"""
    status = project_status(_phase_project(tmp_path, prfaq=True), "p1", tmp_path,
                            view="readiness")

    assert set(status) == {"project", "diagnostic_phase", "readiness"}
    assert status["readiness"]["phase"]["state"] in {"ready", "not_ready", "not_evaluable"}


def test_actions_ask_for_final_slides_once_the_prfaq_is_fresh(tmp_path):
    """PRFAQができた後も候補提案へ戻す行動を出すと、往復が閉じない。"""
    codes = _codes(project_status(_phase_project(tmp_path, prfaq=True), "p1", tmp_path))

    assert "generate_final_slides" in codes and "proceed_to_propose_options" not in codes


def test_no_final_slides_are_asked_for_from_a_stale_prfaq(tmp_path):
    """staleな親から作った資料は即座にstaleを継承する。"""
    codes = _codes(project_status(_phase_project(tmp_path, prfaq="stale"), "p1", tmp_path))

    assert "generate_final_slides" not in codes


def test_actions_request_the_phase_signoff_from_the_decision_maker(tmp_path):
    """承認依頼の宛先が出ないと、誰に持っていくかSkillが判断できない。"""
    actions = project_status(_phase_project(tmp_path, prfaq=True, final=True),
                             "p1", tmp_path)["actions"]
    request = [a for a in actions if a["code"] == "request_phase_signoff"]

    assert request and request[0]["refs"] == ["sh-1"]


def test_regenerated_slides_explain_why_the_signoff_is_needed_again(tmp_path):
    """理由の無い巻き戻りはバグに見える。"""
    storage = _phase_project(tmp_path, prfaq=True, final=True, signoff=True)
    _save_final_slides(storage)  # 承認後にスライドを作り直す
    actions = project_status(storage, "p1", tmp_path)["actions"]
    request = [a for a in actions if a["code"] == "request_phase_signoff"]

    assert request and "再承認" in request[0]["reason"]


def test_actions_report_the_phase_is_complete(tmp_path):
    """完了を返さないと、次フェーズへ進んでよいかが分からない。"""
    codes = _codes(project_status(
        _phase_project(tmp_path, prfaq=True, final=True, signoff=True), "p1", tmp_path))

    assert "complete_phase" in codes


def test_full_view_keeps_the_phase_judgement_inside_readiness(tmp_path):
    """枝の外にトップレベル要素を足すと、投影規則が崩れる。"""
    status = project_status(_phase_project(tmp_path, prfaq=True), "p1", tmp_path,
                            view="full")

    assert "phase_readiness" not in status and "phase" in status["readiness"]


def test_next_step_is_unchanged_by_the_final_stage(tmp_path):
    """フェーズ1のSkillは next_step を完全一致で分岐している。"""
    status = project_status(
        _phase_project(tmp_path, prfaq=True, final=True, signoff=True), "p1", tmp_path)

    assert status["next_step"] in {
        "hearing", "propose-options", "grow-prfaq",
        "regenerate-stale-artifacts", "up-to-date",
    }
