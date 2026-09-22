from datetime import date

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.context import collect, workflow_branch
from medo_core.events import ArtifactTarget, AsIsReportReviewed, StakeholderResponded
from medo_core.nodes import AsIs, Challenge, Stakeholder
from medo_core.requirements import RequirementsDoc, RequirementsStore
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


def _approved_report(storage) -> str:
    report_id = _report(storage)
    slides_id = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=1,
        derived_from=[report_id], generated_by="claude", content="# 討議",
    ))
    WorkflowRecorder(storage).record("p1", AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report_id), occurred_on="2026-08-30",
        requirements_version=1, round_id=0, outcome="approved",
        reviewed_slides_id=slides_id,
    ))
    return report_id


def _save_v2(storage, **sections) -> None:
    """保存済みドキュメントを起点に1セクションだけ差し替える。

    ノードを作り直すとIDが変わり、内容が同じセクションまで変更扱いになる。
    """
    doc = RequirementsStore(storage).get("p1")
    WorkflowRecorder(storage).save_requirements(
        "p1", doc.model_copy(update=sections), today=TODAY,
    )


def test_non_dependent_section_change_keeps_current_target_and_approval(tmp_path):
    """as-is-report が依存しないセクションの更新では、承認済みレビューは有効なまま。"""
    storage = _project(tmp_path)
    report_id = _approved_report(storage)

    _save_v2(storage, challenges=[Challenge(text="人手不足", scope="core")])

    branch = workflow_branch(collect(storage, "p1", include_scope=("core",), today=TODAY))
    assert branch["review"]["current_target"] == report_id
    assert branch["review"]["approved"] is True


def test_dependent_section_change_drops_current_target(tmp_path):
    """依存セクションが変われば内容が古くなるので、現在対象から外す。"""
    storage = _project(tmp_path)
    _approved_report(storage)

    _save_v2(storage, as_is=[AsIs(text="実態が変わった", visibility="internal")])

    branch = workflow_branch(collect(storage, "p1", include_scope=("core",), today=TODAY))
    assert branch["review"]["current_target"] is None
    assert branch["review"]["approved"] is False


def test_historical_freshness_keeps_report_across_non_dependent_change():
    """過去ラウンドの再構成でも、非依存セクションの更新で対象を見失ってはならない。"""
    from medo_core.context import _historical_freshness
    from medo_core.manifest import ChangeManifest, SectionChange

    artifacts = {"as-is-report-v1": Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    )}
    manifests = [ChangeManifest(
        version=2, changes=[SectionChange(section="challenges")], recorded_on="2026-08-30",
    )]

    assert _historical_freshness(artifacts, manifests)["as-is-report-v1"].state == "current"


def test_historical_freshness_marks_dependent_change_stale():
    from medo_core.context import _historical_freshness
    from medo_core.manifest import ChangeManifest, SectionChange

    artifacts = {"as-is-report-v1": Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    )}
    manifests = [ChangeManifest(
        version=2, changes=[SectionChange(section="as_is")], recorded_on="2026-08-30",
    )]

    assert _historical_freshness(artifacts, manifests)["as-is-report-v1"].state == "stale"
