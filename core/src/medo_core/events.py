"""標準周回の進行記録。

要件の中に置くと論理的に破綻する — 要件は保存のたびに版が進むため、
v3への反応を記録するとその保存自体がv4を作り、記録した瞬間に旧版宛てになる。
したがって要件の版とは独立した追記型イベントとして持つ。
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, model_validator

from medo_core.storage import Storage

CheckName = Literal[
    "source_quality", "reality_gap", "past_attempts", "hidden_stakeholders",
    "decision_maker", "internal_consistency", "as_is_articulation",
    "expression_safety", "to_be_articulation", "feasibility", "scope_agreement",
]

MilestoneCondition = Literal[
    "internal_as_is_first_added",
    "perception_gap_added",
    "internal_conflict_gap_added",
    "constraint_added",
    "stalled_attempt_added",
    "resistant_or_decision_maker_added",
    "review_changes_requested",
    "stakeholder_objected",
    "hypothesis_validated",
    "to_be_confirmed",
]


class ArtifactTarget(BaseModel):
    kind: Literal["artifact"] = "artifact"
    artifact_id: str


class RequirementsTarget(BaseModel):
    kind: Literal["requirements"] = "requirements"
    version: int


TargetRef = Annotated[ArtifactTarget | RequirementsTarget, Field(discriminator="kind")]


def _iso_date(value: str) -> str:
    date.fromisoformat(value)
    return value


IsoDate = Annotated[str, AfterValidator(_iso_date)]


class WorkflowEventBase(BaseModel):
    id: str = ""
    target: TargetRef
    occurred_on: IsoDate
    requirements_version: int
    round_id: int


class CheckRecorded(WorkflowEventBase):
    kind: Literal["check"] = "check"
    check: CheckName
    result: Literal["completed", "finding", "undeterminable"]
    note: str = ""
    finding_refs: list[str] = Field(default_factory=list)
    disposition: Literal["open", "deferred", "promoted"] = "open"

    @model_validator(mode="after")
    def _require_evidence_for_non_completed(self) -> "CheckRecorded":
        if self.result == "undeterminable" and not self.note:
            raise ValueError("undeterminable には note(判断できなかった理由)が必須です")
        if self.result == "finding" and not (self.note or self.finding_refs):
            raise ValueError("finding には note または finding_refs が必須です")
        return self


class AsIsReportReviewed(WorkflowEventBase):
    kind: Literal["asis_review"] = "asis_review"
    outcome: Literal["approved", "changes_requested"]
    finding_refs: list[str] = Field(default_factory=list)
    slide_findings: list[str] = Field(default_factory=list)
    reviewed_slides_id: str
    reviewed_by: Literal["claude", "codex", "gemini", "human"] = "human"

    @model_validator(mode="after")
    def _require_findings_when_changes_requested(self) -> "AsIsReportReviewed":
        if self.outcome == "changes_requested" and not (
            self.finding_refs or self.slide_findings
        ):
            raise ValueError(
                "changes_requested には finding_refs または slide_findings が必須です"
            )
        return self


class StakeholderResponded(WorkflowEventBase):
    kind: Literal["response"] = "response"
    stakeholder_id: str
    purpose: Literal["as_is_alignment", "to_be_go_ahead", "phase_signoff"]
    reaction: Literal["empathized", "acknowledged", "agreed", "objected", "unclear"]
    note: str = ""


class MilestoneDetected(WorkflowEventBase):
    kind: Literal["milestone"] = "milestone"
    condition: MilestoneCondition
    focus_hypothesis_id: str = ""


class ToBeCheckpointRecorded(WorkflowEventBase):
    kind: Literal["tobe_checkpoint"] = "tobe_checkpoint"
    answer: Literal["generate", "defer"]
    responds_to: str


WorkflowEvent = Annotated[
    CheckRecorded
    | AsIsReportReviewed
    | StakeholderResponded
    | MilestoneDetected
    | ToBeCheckpointRecorded,
    Field(discriminator="kind"),
]

_EVENT_TYPES = {
    "check": CheckRecorded,
    "asis_review": AsIsReportReviewed,
    "response": StakeholderResponded,
    "milestone": MilestoneDetected,
    "tobe_checkpoint": ToBeCheckpointRecorded,
}


class EventStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _prefix(self, project_id: str) -> str:
        return f"projects/{project_id}/events"

    def append(self, project_id: str, event) -> str:
        numbers = [
            int(p.rsplit("/ev-", 1)[1]) for p in self._storage.list(self._prefix(project_id))
        ]
        event_id = f"ev-{max(numbers, default=0) + 1}"
        event = event.model_copy(update={"id": event_id})
        self._storage.put(
            f"{self._prefix(project_id)}/{event_id}", event.model_dump(mode="json")
        )
        return event_id

    def list(self, project_id: str) -> list:
        events = [self._storage.get(p) for p in self._storage.list(self._prefix(project_id))]
        parsed = [_EVENT_TYPES[raw["kind"]].model_validate(raw) for raw in events]
        return sorted(parsed, key=lambda e: int(e.id.rsplit("-", 1)[1]))
