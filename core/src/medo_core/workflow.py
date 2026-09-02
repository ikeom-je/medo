"""イベント記録の入口。他ストアを参照する検証と節目の自動記録を集約する。

EventStore は要件・生成物を知らない純粋な追記ストアに保つ。
"""

from medo_core.artifacts import ArtifactStore
from medo_core.events import (
    AsIsReportReviewed,
    CheckRecorded,
    EventStore,
    MilestoneDetected,
    StakeholderResponded,
    ToBeCheckpointRecorded,
)
from medo_core.requirements import RequirementsStore
from medo_core.storage import Storage

# purpose → (許容するtarget種別, 生成物の場合の許容type, slide_kind)
PURPOSE_TARGETS = {
    "as_is_alignment": ("artifact", "as-is-report", None),
    "to_be_go_ahead": ("requirements", None, None),
    "phase_signoff": ("artifact", "slides", "final"),
}

EVENT_TARGET_KIND = {
    "asis_review": "artifact",
    "milestone": "requirements",
    "tobe_checkpoint": "requirements",
}


class WorkflowRecorder:
    def __init__(self, storage: Storage):
        self._events = EventStore(storage)
        self._artifacts = ArtifactStore(storage)
        self._requirements = RequirementsStore(storage)

    def record(self, project_id: str, event) -> str:
        existing = self._events.list(project_id)
        duplicate = self._find_duplicate_milestone(event, existing)
        if duplicate:
            return duplicate

        self._validate_target_kind(project_id, event)
        self._validate_references(project_id, event, existing)
        event = event.model_copy(
            update={"round_id": self.round_count(project_id)}
        )
        event_id = self._events.append(project_id, event)
        self._record_event_driven_milestone(project_id, event)
        return event_id

    def round_count(self, project_id: str) -> int:
        """要件履歴を走査し、as_is変更のあと to_be変更が現れたら1周と数える。"""
        from medo_core.manifest import ManifestStore

        round_id = 0
        state = "waiting_as_is"
        for m in ManifestStore(self._requirements._storage).list(project_id):
            sections = {c.section for c in m.changes if c.change_kind == "substantive"}
            if not sections:
                continue
            if state == "waiting_as_is" and "as_is" in sections:
                state = "waiting_to_be"
            if state == "waiting_to_be" and "to_be" in sections:
                round_id += 1
                state = "waiting_as_is"
        return round_id

    def _find_duplicate_milestone(self, event, existing: list) -> str | None:
        if event.kind != "milestone":
            return None
        for e in existing:
            if (
                e.kind == "milestone"
                and e.requirements_version == event.requirements_version
                and e.condition == event.condition
            ):
                return e.id
        return None

    def _validate_target_kind(self, project_id: str, event) -> None:
        expected = EVENT_TARGET_KIND.get(event.kind)
        if expected and event.target.kind != expected:
            raise ValueError(
                f"{event.kind} の target は {expected} である必要があります"
            )
        if event.target.kind == "requirements":
            latest = self._requirements.latest_version(project_id)
            if not 1 <= event.target.version <= latest:
                raise ValueError(
                    f"要件バージョンが存在しません: v{event.target.version}"
                    f"(最新: v{latest})"
                )
        if event.kind == "response":
            kind, artifact_type, slide_kind = PURPOSE_TARGETS[event.purpose]
            if event.target.kind != kind:
                raise ValueError(
                    f"purpose={event.purpose} の target は {kind} である必要があります"
                )

    def _validate_references(self, project_id: str, event, existing: list) -> None:
        if isinstance(event, StakeholderResponded):
            self._validate_response(project_id, event)
        elif isinstance(event, AsIsReportReviewed):
            self._validate_review(project_id, event)
        elif isinstance(event, ToBeCheckpointRecorded):
            self._validate_checkpoint(event, existing)
        elif isinstance(event, CheckRecorded):
            self._validate_check(project_id, event)
        elif isinstance(event, MilestoneDetected) and event.focus_hypothesis_id:
            self._validate_hypothesis(project_id, event.focus_hypothesis_id)

    def _validate_check(self, project_id: str, event: CheckRecorded) -> None:
        """artifact束縛のcheckは、registryが定める型の生成物だけを対象にできる。"""
        try:
            from medo_core.checks import CHECK_REGISTRY
        except ModuleNotFoundError as error:
            if error.name != "medo_core.checks":
                raise
            return

        spec = CHECK_REGISTRY[event.check]
        if spec.binding != "artifact_bound":
            if event.target.kind != "requirements":
                raise ValueError(f"{event.check} の target は requirements です")
            return
        if event.target.kind != "artifact":
            raise ValueError(f"{event.check} の target は artifact です")
        artifact = self._artifacts.get(project_id, event.target.artifact_id)
        if artifact is None or artifact.type != spec.target_type or (
            spec.slide_kind and artifact.slide_kind != spec.slide_kind
        ):
            raise ValueError(
                f"{event.check} の対象は {spec.target_type} である必要があります: "
                f"{event.target.artifact_id}"
            )

    def _validate_hypothesis(self, project_id: str, hypothesis_id: str) -> None:
        doc = self._requirements.get(project_id)
        if not doc or hypothesis_id not in {h.id for h in doc.hypotheses}:
            raise ValueError(f"仮説が存在しません: {hypothesis_id}")

    def _validate_response(self, project_id: str, event: StakeholderResponded) -> None:
        doc = self._requirements.get(project_id)
        if not doc or event.stakeholder_id not in {s.id for s in doc.stakeholders}:
            raise ValueError(f"stakeholder が存在しません: {event.stakeholder_id}")
        _, artifact_type, slide_kind = PURPOSE_TARGETS[event.purpose]
        if artifact_type is None:
            return
        artifact = self._artifacts.get(project_id, event.target.artifact_id)
        if artifact is None:
            raise ValueError(f"生成物が存在しません: {event.target.artifact_id}")
        if artifact.type != artifact_type or (
            slide_kind and artifact.slide_kind != slide_kind
        ):
            raise ValueError(
                f"purpose={event.purpose} の対象は {artifact_type}"
                f"{f'({slide_kind})' if slide_kind else ''} である必要があります"
            )

    def _validate_review(self, project_id: str, event: AsIsReportReviewed) -> None:
        report = self._artifacts.get(project_id, event.target.artifact_id)
        if report is None or report.type != "as-is-report":
            raise ValueError(
                f"レビュー対象は as-is-report である必要があります: {event.target.artifact_id}"
            )
        slides = self._artifacts.get(project_id, event.reviewed_slides_id)
        if (
            slides is None
            or slides.slide_kind != "discussion"
            or event.target.artifact_id not in slides.derived_from
        ):
            raise ValueError(
                "reviewed_slides_id は当該レポートから生成された討議用スライドである"
                f"必要があります: {event.reviewed_slides_id}"
            )
        doc = self._requirements.get(project_id)
        known = {
            n.id
            for section in ("gaps", "challenges", "open_questions")
            for n in getattr(doc, section)
        } if doc else set()
        for ref in event.finding_refs:
            if ref not in known:
                raise ValueError(f"所見の参照先が存在しません: {ref}")

    def _validate_checkpoint(self, event: ToBeCheckpointRecorded, existing: list) -> None:
        milestones = {e.id for e in existing if e.kind == "milestone"}
        if event.responds_to not in milestones:
            raise ValueError(f"節目イベントが存在しません: {event.responds_to}")
        answered = {
            e.responds_to for e in existing if e.kind == "tobe_checkpoint"
        }
        if event.responds_to in answered:
            raise ValueError(f"回答済みの節目です: {event.responds_to}")

    def _record_event_driven_milestone(self, project_id: str, event) -> None:
        """条件7・8。要件保存を伴わずに発生する節目。"""
        condition = None
        if isinstance(event, AsIsReportReviewed) and event.outcome == "changes_requested":
            condition = "review_changes_requested"
        elif isinstance(event, StakeholderResponded) and event.reaction == "objected":
            condition = "stakeholder_objected"
        if condition is None:
            return
        from medo_core.events import RequirementsTarget

        self.record(project_id, MilestoneDetected(
            target=RequirementsTarget(version=event.requirements_version),
            occurred_on=event.occurred_on,
            requirements_version=event.requirements_version,
            round_id=event.round_id,
            condition=condition,
        ))
