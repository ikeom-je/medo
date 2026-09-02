"""イベント記録の入口。他ストアを参照する検証と節目の自動記録を集約する。

EventStore は要件・生成物を知らない純粋な追記ストアに保つ。
"""

from datetime import date

from medo_core.artifacts import ArtifactStore
from medo_core.events import (
    AsIsReportReviewed,
    CheckRecorded,
    EventStore,
    MilestoneDetected,
    StakeholderResponded,
    ToBeCheckpointRecorded,
)
from medo_core.requirements import RequirementsDoc, RequirementsStore
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


def _fermi_variables(artifact) -> set[str]:
    """fermi生成物のモデル変数名。

    content は `{"model": {...}, "result": {...}}` のJSON
    (cli/src/medo_cli/main.py の fermi calc が書く形式)。
    """
    import json

    payload = json.loads(artifact.content)
    return set((payload.get("model", {}).get("variables") or {}).keys())


def detect_milestone(
    previous: RequirementsDoc | None, saved: RequirementsDoc
) -> str | None:
    """要件保存による節目条件(1〜6・9・10)を、最初に成立したもの1件だけ返す。

    単なる本文の微修正や既存項目の言い換えは節目にしない。
    """
    previous = previous or RequirementsDoc(project=saved.project)

    def new_ids(section: str) -> set[str]:
        old = {n.id for n in getattr(previous, section)}
        return {n.id for n in getattr(saved, section)} - old

    if not [a for a in previous.as_is if a.visibility == "internal"] and [
        a for a in saved.as_is if a.visibility == "internal"
    ]:
        return "internal_as_is_first_added"

    added_gaps = [g for g in saved.gaps if g.id in new_ids("gaps")]
    if any(g.kind == "perception" for g in added_gaps):
        return "perception_gap_added"
    if any(g.kind == "internal_conflict" for g in added_gaps):
        return "internal_conflict_gap_added"

    if new_ids("constraints"):
        return "constraint_added"

    added_attempts = [a for a in saved.attempts if a.id in new_ids("attempts")]
    if any(a.outcome in ("stalled", "failed") for a in added_attempts):
        return "stalled_attempt_added"

    added_stakeholders = [s for s in saved.stakeholders if s.id in new_ids("stakeholders")]
    if any(s.stance == "resistant" or s.is_decision_maker for s in added_stakeholders):
        return "resistant_or_decision_maker_added"

    old_hyp = {h.id: h.status for h in previous.hypotheses}
    if any(
        h.status == "validated" and old_hyp.get(h.id) not in (None, "validated")
        for h in saved.hypotheses
    ):
        return "hypothesis_validated"

    old_to_be = {t.id: t.confidence for t in previous.to_be}
    if any(
        t.confidence == "confirmed" and old_to_be.get(t.id) not in (None, "confirmed")
        for t in saved.to_be
    ):
        return "to_be_confirmed"

    return None


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

    def _validate_cross_store_refs(self, project_id: str, doc: RequirementsDoc) -> None:
        """生成物・イベントを参照するフィールドの実在を検証する。"""
        event_ids = {e.id for e in self._events.list(project_id)}
        undeterminable_ids = {
            e.id for e in self._events.list(project_id)
            if e.kind == "check" and e.result == "undeterminable"
        }

        for tb in doc.to_be:
            for ref in tb.evidenced_by:
                if ref.startswith("ev-") and ref not in event_ids:
                    raise ValueError(f"evidenced_by のイベントが存在しません: {ref}")

        for ch in doc.challenges:
            src = ch.promoted_from
            if src and src.kind == "undeterminable" and src.ref not in undeterminable_ids:
                raise ValueError(
                    "promoted_from(undeterminable)の参照先は result='undeterminable' の"
                    f"CheckRecorded である必要があります: {src.ref}"
                )

        for hyp in doc.hypotheses:
            if hyp.fermi_ref is None:
                continue
            artifact = self._artifacts.get(project_id, hyp.fermi_ref.artifact_id)
            if artifact is None or artifact.type != "fermi":
                raise ValueError(
                    f"fermi_ref の参照先が fermi ではありません: "
                    f"{hyp.fermi_ref.artifact_id}"
                )
            if hyp.fermi_ref.variable_name not in _fermi_variables(artifact):
                raise ValueError(
                    "fermi_ref の変数がモデルに存在しません: "
                    f"{hyp.fermi_ref.variable_name}"
                )

    def save_requirements(
        self,
        project_id: str,
        doc: RequirementsDoc,
        *,
        editorial_sections: tuple[str, ...] = (),
        today: date | None = None,
    ) -> int:
        """要件を保存し、節目条件が成立していれば MilestoneDetected を記録する。

        他ストア(生成物・イベント)を参照する検証もここで行う。
        RequirementsStore にそれらを持たせると依存が逆流するため。
        """
        self._validate_cross_store_refs(project_id, doc)
        previous = self._requirements.get(project_id)
        version = self._requirements.save(
            project_id, doc, editorial_sections=editorial_sections, today=today
        )
        saved = self._requirements.get(project_id, version)
        condition = detect_milestone(previous, saved)
        if condition:
            from medo_core.events import RequirementsTarget

            self.record(project_id, MilestoneDetected(
                target=RequirementsTarget(version=version),
                occurred_on=(today or date.today()).isoformat(),
                requirements_version=version,
                round_id=0,
                condition=condition,
            ))
        return version

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
