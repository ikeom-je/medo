from medo_core.checks import (
    CHECK_REGISTRY,
    checks_for_phase,
    detect_inconsistency,
    detect_ritualized,
    effective_checks,
)
from medo_core.events import ArtifactTarget, CheckRecorded, RequirementsTarget
from medo_core.manifest import ChangeManifest, SectionChange
from medo_core.nodes import AsIs, Gap, Stakeholder
from medo_core.requirements import RequirementsDoc


def _recorded(ev_id, check, result, *, round_id=1, requirements_version=1,
              target=None, note="", disposition="open", finding_refs=()):
    ev = CheckRecorded(
        target=target or RequirementsTarget(version=requirements_version),
        occurred_on="2026-08-30", requirements_version=requirements_version,
        round_id=round_id, check=check, result=result, note=note,
        disposition=disposition, finding_refs=list(finding_refs),
    )
    return ev.model_copy(update={"id": ev_id})


def _manifest(version, *sections):
    return ChangeManifest(version=version,
                          changes=[SectionChange(section=s) for s in sections],
                          recorded_on="2026-08-30")


def test_discovery_phase_hides_convergence_checks():
    """初日から全項目を並べると「全部埋めないと動かない」圧を与える。"""
    discovery = set(checks_for_phase("discovery"))

    assert "reality_gap" in discovery
    assert "feasibility" not in discovery


def test_convergence_phase_includes_all_checks():
    assert set(checks_for_phase("convergence")) == set(CHECK_REGISTRY)


def test_unrecorded_check_is_unverified():
    states = effective_checks([], phase="discovery", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert states["reality_gap"].state == "unverified"


def test_persistent_check_survives_requirements_change():
    events = [_recorded("ev-1", "reality_gap", "completed")]

    states = effective_checks(events, phase="discovery", latest_requirements_version=3,
                              manifests=[_manifest(2, "as_is"), _manifest(3, "to_be")],
                              current_artifact_ids={})

    assert states["reality_gap"].state == "completed"


def test_version_bound_check_expires_on_relevant_section_change():
    events = [_recorded("ev-1", "feasibility", "completed")]

    states = effective_checks(events, phase="convergence", latest_requirements_version=2,
                              manifests=[_manifest(2, "constraints")],
                              current_artifact_ids={})

    assert states["feasibility"].state == "unverified"


def test_version_bound_check_survives_unrelated_change():
    events = [_recorded("ev-1", "feasibility", "completed")]

    states = effective_checks(events, phase="convergence", latest_requirements_version=2,
                              manifests=[_manifest(2, "stakeholders")],
                              current_artifact_ids={})

    assert states["feasibility"].state == "completed"


def test_decision_maker_check_expires_when_stakeholders_change():
    events = [_recorded("ev-1", "decision_maker", "completed")]

    states = effective_checks(events, phase="convergence", latest_requirements_version=2,
                              manifests=[_manifest(2, "stakeholders")],
                              current_artifact_ids={})

    assert states["decision_maker"].state == "unverified"


def test_artifact_bound_check_expires_when_target_is_regenerated():
    events = [_recorded("ev-1", "as_is_articulation", "completed",
                        target=ArtifactTarget(artifact_id="as-is-report-v1"))]

    states = effective_checks(events, phase="convergence", latest_requirements_version=1,
                              manifests=[],
                              current_artifact_ids={"as-is-report": "as-is-report-v2"})

    assert states["as_is_articulation"].state == "unverified"


def test_undeterminable_carries_disposition():
    events = [_recorded("ev-1", "to_be_articulation", "undeterminable",
                        note="方向性が未定", disposition="promoted")]

    states = effective_checks(events, phase="convergence", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert states["to_be_articulation"].state == "undeterminable"
    assert states["to_be_articulation"].disposition == "promoted"


def test_finding_without_corresponding_record_is_inconsistent():
    states = effective_checks([_recorded("ev-1", "past_attempts", "finding", note="あり")],
                              phase="discovery", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert "past_attempts" in detect_inconsistency(states, RequirementsDoc(project="p1"))


def test_completed_with_existing_record_is_inconsistent():
    doc = RequirementsDoc(project="p1",
                          stakeholders=[Stakeholder(id="sh-1", text="部長",
                                                    surfaced_by="inferred")])
    states = effective_checks([_recorded("ev-1", "hidden_stakeholders", "completed")],
                              phase="discovery", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert "hidden_stakeholders" in detect_inconsistency(states, doc)


def test_consistent_finding_is_not_reported():
    doc = RequirementsDoc(project="p1",
                          as_is=[AsIs(id="as-1", text="公表", visibility="public"),
                                 AsIs(id="as-2", text="実態", visibility="internal")],
                          gaps=[Gap(id="gap-1", text="乖離", kind="perception",
                                    from_as_is=["as-1", "as-2"])])
    states = effective_checks([_recorded("ev-1", "reality_gap", "finding",
                                         finding_refs=["gap-1"])],
                              phase="discovery", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert detect_inconsistency(states, doc) == []


def test_three_completed_rounds_with_substantive_changes_are_ritualized():
    events = [
        _recorded(f"ev-{n}", "hidden_stakeholders", "completed", round_id=n,
                  requirements_version=n)
        for n in (1, 2, 3)
    ]

    ritualized = detect_ritualized(events, [_manifest(n, "as_is") for n in (1, 2, 3)])

    assert "hidden_stakeholders" in ritualized


def test_completed_rounds_without_changes_are_not_ritualized():
    """ステークホルダーが限定されている案件では completed が続くのが正常。"""
    events = [
        _recorded(f"ev-{n}", "hidden_stakeholders", "completed", round_id=n,
                  requirements_version=n)
        for n in (1, 2, 3)
    ]

    assert detect_ritualized(events, manifests=[]) == []
