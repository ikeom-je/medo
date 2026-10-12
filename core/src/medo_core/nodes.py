"""案件内容のノード型。永続化を持たない純粋なスキーマ。

要件・イベント・診断のすべてが参照するため、Storeを持つモジュールから分離する
(requirements.py に置くと events.py との循環参照になる)。
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Confidence = Literal["confirmed", "assumed", "open"]
Scope = Literal["core", "secondary", "out"]


class Node(BaseModel):
    """IDを持つ案件内容の最小単位。

    id が空文字なら保存時に core が採番する。
    """

    id: str = ""
    text: str
    confidence: Confidence = "open"
    evidence_refs: list[str] = Field(default_factory=list)


class ScopedNode(Node):
    """診断のスコープ絞り込み対象になるノード。

    案件の属性(Kpi / Stakeholder)には scope を付けない。
    """

    scope: Scope = "core"


class PromotionSource(BaseModel):
    """課題の昇格元。矛盾・判断不能が「解くべき課題」になった経緯を残す。"""

    kind: Literal["internal_conflict", "undeterminable"]
    ref: str  # gap-N(internal_conflict) または ev-N(undeterminable)


class AsIs(ScopedNode):
    visibility: Literal["public", "internal"]
    source_stakeholder_ids: list[str] = Field(default_factory=list)
    reality_checked: bool = False


class ToBe(ScopedNode):
    evidenced_by: list[str] = Field(default_factory=list)
    assumed_risks: list[str] = Field(default_factory=list)
    transition_steps: list[str] = Field(default_factory=list)
    journey_before: str = ""
    journey_after: str = ""


class Gap(ScopedNode):
    kind: Literal["perception", "internal_conflict", "goal"] = "goal"
    from_as_is: list[str] = Field(default_factory=list)
    from_to_be: list[str] = Field(default_factory=list)


class Bottleneck(ScopedNode):
    gap_ids: list[str] = Field(default_factory=list)
    from_hypothesis: str = ""


class Challenge(ScopedNode):
    bottleneck_ids: list[str] = Field(default_factory=list)
    cause_hypothesis_ids: list[str] = Field(default_factory=list)
    cost_of_inaction: str = ""
    promoted_from: PromotionSource | None = None


class Constraint(ScopedNode):
    """予算・期間・体制・法令・既存システム。"""


class OpenQuestion(ScopedNode):
    """未確定事項。レビュー所見から参照されるためIDを持つ。"""


class Kpi(Node):
    name: str
    current_fact_id: str = ""
    target_value: float | None = None
    target_text: str = ""
    unit: str = ""
    to_be_ids: list[str] = Field(default_factory=list)


class Stakeholder(Node):
    role: str = ""
    pains: list[str] = Field(default_factory=list)
    stance: Literal["unknown", "supportive", "neutral", "resistant"] = "unknown"
    is_decision_maker: bool = False
    influence: Literal["high", "medium", "low"] = "medium"
    interest: Literal["high", "medium", "low"] = "medium"
    surfaced_by: Literal["stated", "inferred"] = "stated"


BlockerCategory = Literal[
    "resource", "politics_incentive", "technical", "governance", "priority"
]


class Attempt(BaseModel):
    id: str = ""
    challenge_ids: list[str] = Field(default_factory=list)
    gap_ids: list[str] = Field(default_factory=list)
    description: str
    outcome: Literal[
        "not_attempted", "in_progress", "stalled", "failed", "partial", "succeeded"
    ]
    blocker: str = ""
    blocker_category: list[BlockerCategory] = Field(default_factory=list)
    confidence: Confidence = "open"
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_blocker_when_not_progressing(self) -> "Attempt":
        if self.outcome in ("stalled", "failed") and not self.blocker:
            raise ValueError(f"outcome={self.outcome} には blocker が必須です")
        return self


class FermiRef(BaseModel):
    artifact_id: str
    variable_name: str


class Hypothesis(BaseModel):
    id: str = ""
    kind: Literal["cause", "solution", "impact"]
    statement: str
    validation_method: str = ""
    status: Literal["unvalidated", "validating", "validated", "rejected"] = "unvalidated"
    evidence_refs: list[str] = Field(default_factory=list)
    challenge_ids: list[str] = Field(default_factory=list)
    fermi_ref: FermiRef | None = None


ID_PREFIXES = {
    "as_is": "as",
    "to_be": "tb",
    "kpis": "kpi",
    "stakeholders": "sh",
    "gaps": "gap",
    "bottlenecks": "bn",
    "challenges": "ch",
    "constraints": "cs",
    "attempts": "at",
    "hypotheses": "hyp",
    "open_questions": "oq",
}
