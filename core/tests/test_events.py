import pytest
from pydantic import ValidationError

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
from medo_core.storage import LocalJsonStorage


def _check(**kw) -> CheckRecorded:
    base = {
        "target": RequirementsTarget(version=1),
        "occurred_on": "2026-08-30",
        "requirements_version": 1,
        "round_id": 1,
        "check": "reality_gap",
        "result": "completed",
    }
    base.update(kw)
    return CheckRecorded.model_validate(base)


def test_every_event_carries_round_id():
    """round_id が無いと、反応やチェックがどの周回に属するかを一意に決められず
    round_delta を決定論的に算出できない。"""
    assert _check().round_id == 1


def test_target_ref_is_discriminated_by_kind():
    ev = _check(target=ArtifactTarget(artifact_id="as-is-report-v1"))

    assert ev.target.kind == "artifact"
    assert ev.target.artifact_id == "as-is-report-v1"


def test_undeterminable_requires_note():
    with pytest.raises(ValidationError):
        _check(result="undeterminable")


def test_finding_requires_note_or_refs():
    with pytest.raises(ValidationError):
        _check(result="finding")


def test_undeterminable_defaults_to_open_disposition():
    """扱いを決めずに素通りできないよう、既定は収束をブロックする open。"""
    ev = _check(result="undeterminable", note="組織として方向性が未定")

    assert ev.disposition == "open"


def test_review_requires_findings_when_changes_requested():
    with pytest.raises(ValidationError):
        AsIsReportReviewed(
            target=ArtifactTarget(artifact_id="as-is-report-v1"),
            occurred_on="2026-08-30", requirements_version=1, round_id=1,
            outcome="changes_requested", reviewed_slides_id="slides-v1",
        )


def test_review_accepts_slide_only_findings():
    """スライド固有の差し戻しを要件ノードで表せないため、自由文の枠を持つ。"""
    ev = AsIsReportReviewed(
        target=ArtifactTarget(artifact_id="as-is-report-v1"),
        occurred_on="2026-08-30", requirements_version=1, round_id=1,
        outcome="changes_requested", reviewed_slides_id="slides-v1",
        slide_findings=["見出しが非難調になっている"],
    )

    assert ev.finding_refs == []


def test_append_assigns_monotonic_event_ids(tmp_path):
    store = EventStore(LocalJsonStorage(tmp_path))

    assert store.append("p1", _check()) == "ev-1"
    assert store.append("p1", _check()) == "ev-2"


def test_list_returns_events_in_id_order(tmp_path):
    store = EventStore(LocalJsonStorage(tmp_path))
    for _ in range(11):
        store.append("p1", _check())

    assert [e.id for e in store.list("p1")][:2] == ["ev-1", "ev-2"]
    assert store.list("p1")[-1].id == "ev-11"


def test_events_of_different_kinds_round_trip(tmp_path):
    store = EventStore(LocalJsonStorage(tmp_path))
    store.append("p1", _check())
    store.append("p1", MilestoneDetected(
        target=RequirementsTarget(version=1), occurred_on="2026-08-30",
        requirements_version=1, round_id=1, condition="internal_as_is_first_added",
    ))

    kinds = [e.kind for e in store.list("p1")]
    assert kinds == ["check", "milestone"]

def test_response_records_what_the_agreement_was_about():
    """同じagreedでも「現状認識に納得」と「次工程を承認」は別物。"""
    ev = StakeholderResponded(
        target=ArtifactTarget(artifact_id="as-is-report-v1"), occurred_on="2026-08-30",
        requirements_version=1, round_id=1,
        stakeholder_id="sh-1", purpose="to_be_go_ahead", reaction="agreed",
    )

    assert ev.purpose == "to_be_go_ahead"
    assert ev.kind == "response"


def test_checkpoint_answer_points_at_the_milestone_it_answers():
    """未回答は「対応する回答を持たない節目」として一意に導く必要がある。"""
    ev = ToBeCheckpointRecorded(
        target=RequirementsTarget(version=1), occurred_on="2026-08-30",
        requirements_version=1, round_id=1, answer="generate", responds_to="ev-3",
    )

    assert ev.responds_to == "ev-3"


def test_occurred_on_rejects_a_non_iso_date():
    """日付が自由文だと、周回や祖先の判定が後から追えなくなる。"""
    with pytest.raises(ValidationError):
        _check(occurred_on="2026/08/30")
