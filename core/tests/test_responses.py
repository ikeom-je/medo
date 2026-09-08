from medo_core.artifacts import Artifact
from medo_core.events import ArtifactTarget, RequirementsTarget, StakeholderResponded
from medo_core.manifest import ChangeManifest, SectionChange
from medo_core.responses import (
    ConvergenceTarget,
    fold_responses,
    resolve_convergence_target,
)


def _artifact(a_id: str, requirements_version: int, type_="as-is-report") -> Artifact:
    version = int(a_id.rsplit("-v", 1)[1])
    return Artifact(project="p1", type=type_, version=version,
                    requirements_version=requirements_version,
                    generated_by="claude", content="x")


def _response(ev_id, stakeholder, purpose, reaction, target, round_id=1):
    ev = StakeholderResponded(
        target=target, occurred_on="2026-08-30", requirements_version=1,
        round_id=round_id, stakeholder_id=stakeholder, purpose=purpose, reaction=reaction,
    )
    return ev.model_copy(update={"id": ev_id})


def _manifest(version, *sections):
    return ChangeManifest(
        version=version,
        changes=[SectionChange(section=s) for s in sections],
        recorded_on="2026-08-30",
    )


def test_convergence_target_picks_report_generated_from_latest_version():
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1),
                 "as-is-report-v2": _artifact("as-is-report-v2", 2)}

    target = resolve_convergence_target(2, artifacts)

    assert target == ConvergenceTarget(requirements_version=2,
                                       as_is_report_id="as-is-report-v2")


def test_convergence_target_is_none_when_no_report_from_latest_version():
    """古い要件から作られたレポートを現在対象にすると両者が食い違う。"""
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1)}

    assert resolve_convergence_target(2, artifacts).as_is_report_id is None


def test_response_to_ancestor_is_superseded_by_response_to_current_target():
    """v1で異議が出た後にv2で修正して合意を得ても、v1の異議が永久に残ってはならない。"""
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1),
                 "as-is-report-v2": _artifact("as-is-report-v2", 2)}
    events = [
        _response("ev-1", "sh-1", "as_is_alignment", "objected",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
        _response("ev-2", "sh-1", "as_is_alignment", "agreed",
                  ArtifactTarget(artifact_id="as-is-report-v2")),
    ]

    effective = fold_responses(events, resolve_convergence_target(2, artifacts),
                               artifacts, manifests=[])

    assert [(e.stakeholder_id, e.reaction, e.event_id) for e in effective] == [
        ("sh-1", "agreed", "ev-2")
    ]


def test_current_target_response_wins_over_later_recorded_ancestor_response():
    """記録の順序ではなく対象の新しさで優先する。"""
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1),
                 "as-is-report-v2": _artifact("as-is-report-v2", 2)}
    events = [
        _response("ev-1", "sh-1", "as_is_alignment", "agreed",
                  ArtifactTarget(artifact_id="as-is-report-v2")),
        _response("ev-2", "sh-1", "as_is_alignment", "objected",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
    ]

    effective = fold_responses(events, resolve_convergence_target(2, artifacts),
                               artifacts, manifests=[])

    assert effective[0].event_id == "ev-1"


def test_ancestor_agreement_expires_when_its_own_sections_change():
    events = [_response("ev-1", "sh-1", "to_be_go_ahead", "agreed",
                        RequirementsTarget(version=1))]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=2, as_is_report_id=None),
                               artifacts={}, manifests=[_manifest(2, "to_be")])

    assert effective[0].expired is True


def test_ancestor_agreement_survives_unrelated_section_change():
    """無関係なconstraints追記で合意が巻き添え失効すると収束不能ループに陥る。"""
    events = [_response("ev-1", "sh-1", "to_be_go_ahead", "agreed",
                        RequirementsTarget(version=1))]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=2, as_is_report_id=None),
                               artifacts={}, manifests=[_manifest(2, "constraints")])

    assert effective[0].expired is False


def test_objection_survives_content_change():
    """解消が確認できるまで残す。安全側に倒す。"""
    events = [_response("ev-1", "sh-1", "to_be_go_ahead", "objected",
                        RequirementsTarget(version=1))]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=2, as_is_report_id=None),
                               artifacts={}, manifests=[_manifest(2, "to_be")])

    assert effective[0].expired is False


def test_higher_purpose_agreement_subsumes_lower_purpose_objection():
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1)}
    events = [
        _response("ev-1", "sh-1", "as_is_alignment", "objected",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
        _response("ev-2", "sh-1", "to_be_go_ahead", "agreed",
                  RequirementsTarget(version=1)),
    ]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=1,
                                                 as_is_report_id="as-is-report-v1"),
                               artifacts, manifests=[])

    objection = next(e for e in effective if e.purpose == "as_is_alignment")
    assert objection.subsumed_by == "ev-2"


def test_responses_of_different_stakeholders_are_folded_independently():
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1)}
    events = [
        _response("ev-1", "sh-1", "as_is_alignment", "agreed",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
        _response("ev-2", "sh-2", "as_is_alignment", "objected",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
    ]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=1,
                                                 as_is_report_id="as-is-report-v1"),
                               artifacts, manifests=[])

    assert len(effective) == 2


def test_signoff_on_regenerated_slides_is_not_inherited():
    """何を見て承認したかが一意に定まる必要がある。スライドを作り直したら
    旧スライドへの承認は現在対象への承認として数えない。"""
    def _slide(v):
        return Artifact(project="p1", type="slides", slide_kind="final", version=v,
                        requirements_version=1, generated_by="claude", content="x")

    artifacts = {"slides-v1": _slide(1), "slides-v2": _slide(2)}
    events = [_response("ev-1", "sh-1", "phase_signoff", "agreed",
                        ArtifactTarget(artifact_id="slides-v1"))]

    effective = fold_responses(events, resolve_convergence_target(1, artifacts),
                               artifacts, manifests=[])

    assert effective[0].on_current_target is False


def test_signoff_on_current_slides_counts():
    def _slide(v):
        return Artifact(project="p1", type="slides", slide_kind="final", version=v,
                        requirements_version=1, generated_by="claude", content="x")

    artifacts = {"slides-v1": _slide(1)}
    events = [_response("ev-1", "sh-1", "phase_signoff", "agreed",
                        ArtifactTarget(artifact_id="slides-v1"))]

    effective = fold_responses(events, resolve_convergence_target(1, artifacts),
                               artifacts, manifests=[])

    assert effective[0].on_current_target is True


def test_ancestor_empathy_expires_like_agreement():
    """共感も合意と同じく、依存セクションが変われば失効する。"""
    events = [_response("ev-1", "sh-1", "to_be_go_ahead", "empathized",
                        RequirementsTarget(version=1))]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=2, as_is_report_id=None),
                               artifacts={}, manifests=[_manifest(2, "to_be")])

    assert effective[0].expired is True
