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
from medo_core.nodes import AsIs, Stakeholder
from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.storage import LocalJsonStorage
from medo_core.workflow import WorkflowRecorder

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
