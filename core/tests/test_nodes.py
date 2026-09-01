import pytest
from pydantic import ValidationError

from medo_core.nodes import (
    ID_PREFIXES,
    AsIs,
    Bottleneck,
    Challenge,
    Gap,
    Node,
    PromotionSource,
    ScopedNode,
    ToBe,
)
from medo_core.nodes import Attempt, FermiRef, Hypothesis, Kpi, Stakeholder


def test_node_defaults_to_open_confidence_and_empty_id():
    node = Node(text="現状は手作業")

    assert node.id == ""
    assert node.confidence == "open"
    assert node.evidence_refs == []


def test_scoped_node_defaults_to_core_scope():
    node = ScopedNode(text="現状は手作業")

    assert node.scope == "core"


def test_as_is_requires_explicit_visibility():
    """既定値を持たせると、指定漏れの公開情報が内部実態として扱われ
    認識GAPの検出が壊れる。"""
    with pytest.raises(ValidationError):
        AsIs(text="紙の伝票を手入力している")


def test_as_is_records_reality_checked_separately_from_gap():
    node = AsIs(text="DX推進中と公表", visibility="public", reality_checked=True)

    assert node.reality_checked is True


def test_to_be_holds_business_journey_before_and_after():
    """抽象的な状態記述だけでは顧客が訂正できないため、具体シナリオを持つ。"""
    node = ToBe(
        text="伝票処理が自動化されている",
        journey_before="朝9時に担当者が紙の伝票を手入力する",
        journey_after="朝9時にシステムが取り込み、担当者は例外のみ確認する",
    )

    assert node.journey_before.startswith("朝9時")


def test_gap_defaults_to_goal_kind():
    assert Gap(text="乖離がある").kind == "goal"


def test_bottleneck_records_promoting_hypothesis():
    node = Bottleneck(text="承認が3階層ある", confidence="confirmed", from_hypothesis="hyp-1")

    assert node.from_hypothesis == "hyp-1"


def test_challenge_can_record_promotion_source_as_typed_value():
    """生の文字列だと任意のイベントからでも昇格扱いにできてしまう。"""
    node = Challenge(
        text="どちらの実態を前提にするか",
        promoted_from=PromotionSource(kind="internal_conflict", ref="gap-3"),
    )

    assert node.promoted_from.kind == "internal_conflict"


def test_id_prefixes_cover_every_numbered_section():
    assert ID_PREFIXES["as_is"] == "as"
    assert ID_PREFIXES["to_be"] == "tb"
    assert set(ID_PREFIXES) == {
        "as_is", "to_be", "kpis", "stakeholders", "gaps", "bottlenecks",
        "challenges", "constraints", "attempts", "hypotheses", "open_questions",
    }


def test_kpi_holds_current_value_as_fact_reference_not_number():
    """現状値は観測された事実。数値の通り道にLLMを挟まないため fact を参照する。"""
    kpi = Kpi(text="受注リードタイム", name="lead_time", current_fact_id="fact-3",
              target_value=2.0, unit="日")

    assert kpi.current_fact_id == "fact-3"
    assert not hasattr(kpi, "current_value")


def test_kpi_has_no_scope_attribute():
    """scope は作業対象ノードだけが持つ。案件の属性には適用しない。"""
    assert "scope" not in Kpi.model_fields


def test_stakeholder_separates_influence_from_decision_authority():
    """案件を頓挫させるのは「決裁権はないが拒否権を持つ実力者」。"""
    sh = Stakeholder(text="情報システム部長", is_decision_maker=False, influence="high")

    assert sh.is_decision_maker is False
    assert sh.influence == "high"


def test_stakeholder_defaults_to_stated_discovery_path():
    assert Stakeholder(text="現場担当").surfaced_by == "stated"


def test_attempt_distinguishes_not_attempted_from_unknown():
    """「取り組んでいない」という確認済みの事実と、未確認の空欄を区別する。"""
    attempt = Attempt(description="検討したことがない", outcome="not_attempted")

    assert attempt.outcome == "not_attempted"


def test_attempt_requires_blocker_when_stalled():
    """頓挫理由は制約とボトルネックの最有力の発見源。"""
    with pytest.raises(ValidationError):
        Attempt(description="RPA導入を試みた", outcome="stalled")


def test_attempt_requires_blocker_when_failed():
    with pytest.raises(ValidationError):
        Attempt(description="RPA導入を試みた", outcome="failed")


def test_attempt_accepts_blocker_category_for_root_cause_direction():
    attempt = Attempt(
        description="RPA導入を試みた",
        outcome="stalled",
        blocker="情報システム部が反対した",
        blocker_category=["politics_incentive"],
    )

    assert attempt.blocker_category == ["politics_incentive"]


def test_hypothesis_connects_impact_to_fermi_variable():
    hyp = Hypothesis(
        kind="impact",
        statement="転記工数が半減する",
        fermi_ref=FermiRef(artifact_id="fermi-v2", variable_name="transcription_hours"),
    )

    assert hyp.fermi_ref.variable_name == "transcription_hours"
