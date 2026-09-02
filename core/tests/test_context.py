from datetime import date

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.context import collect, workflow_branch
from medo_core.events import ArtifactTarget, AsIsReportReviewed, StakeholderResponded
from medo_core.nodes import AsIs, Stakeholder
from medo_core.requirements import RequirementsDoc
from medo_core.storage import LocalJsonStorage
from medo_core.workflow import WorkflowRecorder

TODAY = date(2026, 8, 30)


def _project(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    WorkflowRecorder(storage).save_requirements("p1", RequirementsDoc(
        project="p1",
        as_is=[AsIs(text="実態", visibility="internal")],
        stakeholders=[Stakeholder(text="部長", is_decision_maker=True)],
    ), today=TODAY)
    return storage


def _report(storage, requirements_version=1) -> str:
    return ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=requirements_version,
        generated_by="claude", content="# 現状",
    ))


def test_collect_resolves_current_target_from_latest_version(tmp_path):
    storage = _project(tmp_path)
    report_id = _report(storage)

    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    assert ctx.target.as_is_report_id == report_id


def test_collect_reports_unanswered_milestone(tmp_path):
    """未回答は「対応する回答を持たない MilestoneDetected」として一意に導く。"""
    storage = _project(tmp_path)

    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    assert len(ctx.pending_milestones) == 1


def test_collect_clears_pending_after_checkpoint_answer(tmp_path):
    from medo_core.events import RequirementsTarget, ToBeCheckpointRecorded

    storage = _project(tmp_path)
    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)
    WorkflowRecorder(storage).record("p1", ToBeCheckpointRecorded(
        target=RequirementsTarget(version=1), occurred_on="2026-08-30",
        requirements_version=1, round_id=0, answer="generate",
        responds_to=ctx.pending_milestones[0],
    ))

    assert collect(storage, "p1", include_scope=("core",), today=TODAY).pending_milestones == []


def test_open_review_finding_is_cleared_by_approval_of_successor(tmp_path):
    """収束条件は「レビューがある」ではなく「未解決の差し戻しが無い」。"""
    storage = _project(tmp_path)
    report_v1 = _report(storage)
    slides_v1 = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=1,
        derived_from=[report_v1], generated_by="claude", content="# 討議",
    ))
    rec = WorkflowRecorder(storage)
    rec.record("p1", AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report_v1), occurred_on="2026-08-30",
        requirements_version=1, round_id=0, outcome="changes_requested",
        reviewed_slides_id=slides_v1, slide_findings=["見出しが非難調"],
    ))
    assert collect(storage, "p1", include_scope=("core",),
                   today=TODAY).open_review_findings != []

    report_v2 = _report(storage)
    slides_v2 = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=1,
        derived_from=[report_v2], generated_by="claude", content="# 討議2",
    ))
    rec.record("p1", AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report_v2), occurred_on="2026-08-31",
        requirements_version=1, round_id=0, outcome="approved",
        reviewed_slides_id=slides_v2,
    ))

    assert collect(storage, "p1", include_scope=("core",),
                   today=TODAY).open_review_findings == []


def test_resolved_objections_counts_objections_no_longer_effective(tmp_path):
    storage = _project(tmp_path)
    report_v1 = _report(storage)
    rec = WorkflowRecorder(storage)
    rec.record("p1", StakeholderResponded(
        target=ArtifactTarget(artifact_id=report_v1), occurred_on="2026-08-30",
        requirements_version=1, round_id=0,
        stakeholder_id="sh-1", purpose="as_is_alignment", reaction="objected",
    ))
    report_v2 = _report(storage)
    rec.record("p1", StakeholderResponded(
        target=ArtifactTarget(artifact_id=report_v2), occurred_on="2026-08-31",
        requirements_version=1, round_id=0,
        stakeholder_id="sh-1", purpose="as_is_alignment", reaction="agreed",
    ))

    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    assert ctx.resolved_objections == 1


def test_workflow_branch_reports_divergence_after_two_empty_rounds(tmp_path):
    """発散は停止条件ではなく、論点を絞る合図として報告する。"""
    storage = _project(tmp_path)
    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    branch = workflow_branch(ctx)

    assert branch["loop"]["divergence_warning"] is False


def test_workflow_branch_carries_checks_and_responses(tmp_path):
    storage = _project(tmp_path)
    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    branch = workflow_branch(ctx)

    assert set(branch) == {"checks", "review", "responses", "loop"}
    assert "states" in branch["checks"]
