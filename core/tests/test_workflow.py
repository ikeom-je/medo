import json
from datetime import date

import pytest

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.events import (
    ArtifactTarget,
    AsIsReportReviewed,
    CheckRecorded,
    EventStore,
    MilestoneDetected,
    RequirementsTarget,
    StakeholderResponded,
    ToBeCheckpointRecorded,
)
from medo_core.nodes import AsIs, Attempt, Constraint, Hypothesis, Stakeholder, ToBe
from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.storage import LocalJsonStorage
from medo_core.workflow import WorkflowRecorder, detect_milestone

TODAY = "2026-08-30"          # イベントの occurred_on(ISO文字列)
TODAY_DATE = date(2026, 8, 30)  # 要件保存の today(date型)


@pytest.fixture
def project(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    reqs = RequirementsStore(storage)
    reqs.save("p1", RequirementsDoc(
        project="p1",
        as_is=[AsIs(text="紙の伝票を手入力", visibility="internal")],
        stakeholders=[Stakeholder(text="情報システム部長", is_decision_maker=True)],
    ))
    return storage


def _recorder(storage) -> WorkflowRecorder:
    return WorkflowRecorder(storage)


def test_record_assigns_round_id_from_requirements_history(project):
    ev_id = _recorder(project).record("p1", CheckRecorded(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, check="reality_gap", result="completed",
    ))

    stored = EventStore(project).list("p1")[0]
    assert stored.id == ev_id
    assert stored.round_id == 0


def test_record_rejects_target_pointing_to_nonexistent_version(project):
    """存在しない版を対象にすると、畳み込みの祖先判定が壊れる。"""
    with pytest.raises(ValueError, match="v9"):
        _recorder(project).record("p1", CheckRecorded(
            target=RequirementsTarget(version=9), occurred_on=TODAY,
            requirements_version=1, round_id=0, check="reality_gap", result="completed",
        ))


def test_record_rejects_response_for_unknown_stakeholder(project):
    ArtifactStore(project).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))

    with pytest.raises(ValueError, match="sh-99"):
        _recorder(project).record("p1", StakeholderResponded(
            target=ArtifactTarget(artifact_id="as-is-report-v1"), occurred_on=TODAY,
            requirements_version=1, round_id=0,
            stakeholder_id="sh-99", purpose="as_is_alignment", reaction="agreed",
        ))


def test_record_rejects_purpose_target_mismatch(project):
    """to_be_go_ahead は要件を対象にする。生成物宛てを許すと畳み込みが壊れる。"""
    ArtifactStore(project).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))

    with pytest.raises(ValueError, match="to_be_go_ahead"):
        _recorder(project).record("p1", StakeholderResponded(
            target=ArtifactTarget(artifact_id="as-is-report-v1"), occurred_on=TODAY,
            requirements_version=1, round_id=0,
            stakeholder_id="sh-1", purpose="to_be_go_ahead", reaction="agreed",
        ))


def test_record_rejects_review_of_non_report_artifact(project):
    ArtifactStore(project).save("p1", Artifact(
        project="p1", type="research", requirements_version=1,
        generated_by="claude", content="調査",
    ))

    with pytest.raises(ValueError, match="as-is-report"):
        _recorder(project).record("p1", AsIsReportReviewed(
            target=ArtifactTarget(artifact_id="research-v1"), occurred_on=TODAY,
            requirements_version=1, round_id=0, outcome="approved",
            reviewed_slides_id="slides-v1",
        ))


def test_record_requires_reviewed_slides_derived_from_the_report(project):
    """レポートとスライドを必ず一緒にレビューする契約と整合させる。"""
    store = ArtifactStore(project)
    store.save("p1", Artifact(project="p1", type="as-is-report", requirements_version=1,
                              generated_by="claude", content="# 現状"))
    store.save("p1", Artifact(project="p1", type="research", requirements_version=1,
                              generated_by="claude", content="調査"))

    with pytest.raises(ValueError, match="reviewed_slides_id"):
        _recorder(project).record("p1", AsIsReportReviewed(
            target=ArtifactTarget(artifact_id="as-is-report-v1"), occurred_on=TODAY,
            requirements_version=1, round_id=0, outcome="approved",
            reviewed_slides_id="research-v1",
        ))


def test_record_rejects_double_answer_to_same_milestone(project):
    rec = _recorder(project)
    ms_id = rec.record("p1", MilestoneDetected(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, condition="constraint_added",
    ))
    rec.record("p1", ToBeCheckpointRecorded(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, answer="generate", responds_to=ms_id,
    ))

    with pytest.raises(ValueError, match="回答済み"):
        rec.record("p1", ToBeCheckpointRecorded(
            target=RequirementsTarget(version=1), occurred_on=TODAY,
            requirements_version=1, round_id=0, answer="defer", responds_to=ms_id,
        ))


def test_record_deduplicates_milestone_by_version_and_condition(project):
    """要件保存後のイベント記録失敗に備え、再試行しても重複しない。"""
    rec = _recorder(project)
    first = rec.record("p1", MilestoneDetected(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, condition="constraint_added",
    ))
    second = rec.record("p1", MilestoneDetected(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, condition="constraint_added",
    ))

    assert first == second
    assert len(EventStore(project).list("p1")) == 1


def test_objection_records_milestone_automatically(project):
    """条件8は要件保存を伴わずに発生するため、イベント記録自体が節目を作る。"""
    ArtifactStore(project).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))
    rec = _recorder(project)
    rec.record("p1", StakeholderResponded(
        target=ArtifactTarget(artifact_id="as-is-report-v1"), occurred_on=TODAY,
        requirements_version=1, round_id=0,
        stakeholder_id="sh-1", purpose="as_is_alignment", reaction="objected",
    ))

    conditions = [e.condition for e in EventStore(project).list("p1") if e.kind == "milestone"]
    assert conditions == ["stakeholder_objected"]


def _saved(storage, **kw) -> int:
    doc = RequirementsDoc(project="p1", **kw)
    return WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)


def test_detects_first_internal_as_is(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    _saved(storage, as_is=[AsIs(text="公表", visibility="public")])
    doc = RequirementsStore(storage).get("p1")
    doc.as_is.append(AsIs(text="実は手作業", visibility="internal"))
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["internal_as_is_first_added"]


def test_detects_new_constraint(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    _saved(storage)
    doc = RequirementsStore(storage).get("p1")
    doc.constraints.append(Constraint(text="親会社の内規で外部SaaS禁止"))
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["constraint_added"]


def test_detects_stalled_attempt(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    _saved(storage)
    doc = RequirementsStore(storage).get("p1")
    doc.attempts.append(Attempt(description="RPA導入", outcome="stalled",
                                blocker="情シスが反対"))
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["stalled_attempt_added"]


def test_detects_to_be_promoted_to_confirmed(tmp_path):
    """順調に進んで案が固まったときも等しく重大な分岐点である。"""
    storage = LocalJsonStorage(tmp_path)
    _saved(storage, to_be=[ToBe(text="自動化されている", confidence="assumed")])
    doc = RequirementsStore(storage).get("p1")
    doc.to_be[0] = doc.to_be[0].model_copy(update={"confidence": "confirmed"})
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["to_be_confirmed"]


def test_detects_hypothesis_validated(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    _saved(storage, hypotheses=[Hypothesis(kind="cause", statement="承認階層が原因")])
    doc = RequirementsStore(storage).get("p1")
    doc.hypotheses[0] = doc.hypotheses[0].model_copy(update={"status": "validated"})
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["hypothesis_validated"]


def test_records_only_one_milestone_when_several_conditions_hold(tmp_path):
    """1回の保存に対して問いかけは1回でよい。"""
    storage = LocalJsonStorage(tmp_path)
    _saved(storage)
    doc = RequirementsStore(storage).get("p1")
    doc.as_is.append(AsIs(text="実は手作業", visibility="internal"))
    doc.constraints.append(Constraint(text="予算300万円"))
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    milestones = [e for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert len(milestones) == 1
    assert milestones[0].condition == "internal_as_is_first_added"


def test_text_only_edit_is_not_a_milestone(tmp_path):
    """本文の精緻化そのものは節目にしない。初回保存で立った節目と区別する。"""
    storage = LocalJsonStorage(tmp_path)
    _saved(storage, as_is=[AsIs(text="手作業", visibility="internal")])
    before = len([e for e in EventStore(storage).list("p1") if e.kind == "milestone"])

    doc = RequirementsStore(storage).get("p1")
    doc.as_is[0] = doc.as_is[0].model_copy(update={"text": "紙の伝票を手入力"})
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    after = [e for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert len(after) == before


def test_save_requirements_rejects_fermi_ref_to_missing_variable(tmp_path):
    """数値の接続点が壊れていると、感度分析が別の変数を指すまま通ってしまう。"""
    from medo_core.nodes import FermiRef, Hypothesis

    storage = LocalJsonStorage(tmp_path)
    ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="fermi", requirements_version=1,
        content=json.dumps({
            "model": {"name": "工数", "formula": "transcription_hours * 12",
                      "variables": {"transcription_hours": {"assume": 120}}},
            "result": {"name": "工数", "value": 1440, "resolved": {}},
        }),
    ))
    doc = RequirementsDoc(project="p1", hypotheses=[Hypothesis(
        kind="impact", statement="半減する",
        fermi_ref=FermiRef(artifact_id="fermi-v1", variable_name="unknown_var"),
    )])

    with pytest.raises(ValueError, match="unknown_var"):
        WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)


def test_save_requirements_rejects_promotion_from_non_undeterminable_event(tmp_path):
    from medo_core.nodes import Challenge, PromotionSource

    storage = LocalJsonStorage(tmp_path)
    doc = RequirementsDoc(project="p1", challenges=[Challenge(
        text="方向性が定まっていない",
        promoted_from=PromotionSource(kind="undeterminable", ref="ev-99"),
    )])

    with pytest.raises(ValueError, match="ev-99"):
        WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)


def test_save_requirements_rejects_evidenced_by_to_missing_event(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    doc = RequirementsDoc(project="p1",
                          to_be=[ToBe(text="自動化", evidenced_by=["ev-99"])])

    with pytest.raises(ValueError, match="ev-99"):
        WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)


def test_detect_milestone_fires_on_first_save_with_internal_as_is():
    """「0件→1件以上」は初回保存でも成立する。"""
    saved = RequirementsDoc(project="p1",
                            as_is=[AsIs(id="as-1", text="実態", visibility="internal")])

    assert detect_milestone(None, saved) == "internal_as_is_first_added"


def test_detect_milestone_returns_none_for_empty_first_save():
    assert detect_milestone(None, RequirementsDoc(project="p1")) is None
