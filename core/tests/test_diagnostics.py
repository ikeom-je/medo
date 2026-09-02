from medo_core.artifacts import GrownFrom
from medo_core.checks import CheckState
from medo_core.diagnostics import (
    diagnostic_phase,
    model_diagnostics,
    phase_readiness,
    readiness,
    round_delta,
)
from medo_core.nodes import (
    AsIs, Attempt, Bottleneck, Challenge, Gap, Hypothesis, Kpi, PromotionSource,
    Stakeholder, ToBe,
)
from medo_core.requirements import RequirementsDoc
from medo_core.responses import ConvergenceTarget, EffectiveResponse


def _doc(**kw) -> RequirementsDoc:
    return RequirementsDoc(project="p1", **kw)


def _model(doc, include_scope=("core",)) -> dict:
    return model_diagnostics(doc, artifacts={}, freshness={}, include_scope=include_scope)


def test_phase_is_discovery_until_first_to_be():
    """探索の初期に収束警告を出すと「全部埋めないと動かない」印象を与える。"""
    assert diagnostic_phase(_doc()) == "discovery"


def test_phase_becomes_convergence_when_to_be_exists():
    assert diagnostic_phase(_doc(to_be=[ToBe(id="tb-1", text="自動化")])) == "convergence"


def test_structure_counts_as_is_by_visibility():
    doc = _doc(as_is=[
        AsIs(id="as-1", text="公表", visibility="public"),
        AsIs(id="as-2", text="実態", visibility="internal", confidence="confirmed"),
    ])

    structure = _model(doc)["structure"]["as_is"]
    assert structure == {"count": 2, "confirmed": 1, "public": 1, "internal": 1}


def test_structure_excludes_out_of_scope_nodes_by_default():
    doc = _doc(challenges=[
        Challenge(id="ch-1", text="今回の課題"),
        Challenge(id="ch-2", text="今回は扱わない", scope="secondary"),
    ])

    assert _model(doc)["structure"]["challenges"]["count"] == 1


def test_include_scope_widens_the_diagnostic_range():
    doc = _doc(challenges=[
        Challenge(id="ch-1", text="今回の課題"),
        Challenge(id="ch-2", text="今回は扱わない", scope="secondary"),
    ])

    widened = _model(doc, include_scope=("core", "secondary"))
    assert widened["structure"]["challenges"]["count"] == 2


def test_scope_filter_does_not_apply_to_kpis():
    """scope を持たない型は常に全件が対象。"""
    doc = _doc(kpis=[Kpi(id="kpi-1", text="リードタイム", name="lead_time")])

    assert _model(doc)["structure"]["kpis"]["count"] == 1


def test_links_report_challenge_without_any_cause():
    doc = _doc(challenges=[Challenge(id="ch-1", text="後戻りが起きる")])

    assert _model(doc)["links"]["challenges_without_cause"] == ["ch-1"]


def test_links_exclude_promoted_challenge_from_cause_check():
    """昇格した課題は矛盾や判断不能が起点なので、真因リンクが空でも正常。"""
    doc = _doc(challenges=[Challenge(
        id="ch-1", text="どちらを前提にするか",
        promoted_from=PromotionSource(kind="internal_conflict", ref="gap-1"),
    )])

    assert _model(doc)["links"]["challenges_without_cause"] == []


def test_links_report_goal_gap_without_bottleneck():
    doc = _doc(gaps=[Gap(id="gap-1", text="乖離", kind="goal"),
                     Gap(id="gap-2", text="認識差", kind="perception")])

    assert _model(doc)["links"]["gaps_without_bottleneck"] == ["gap-1"]


def test_links_report_to_be_not_referenced_by_any_kpi():
    doc = _doc(to_be=[ToBe(id="tb-1", text="自動化"), ToBe(id="tb-2", text="即時化")],
               kpis=[Kpi(id="kpi-1", text="LT", name="lt", to_be_ids=["tb-1"])])

    assert _model(doc)["links"]["to_be_without_kpi"] == ["tb-2"]


def test_links_report_unvalidated_hypotheses():
    doc = _doc(hypotheses=[
        Hypothesis(id="hyp-1", kind="cause", statement="a"),
        Hypothesis(id="hyp-2", kind="cause", statement="b", status="validated"),
    ])

    assert _model(doc)["links"]["hypotheses_unvalidated"] == ["hyp-1"]


def test_coverage_reports_public_as_is_never_checked_against_reality():
    doc = _doc(as_is=[AsIs(id="as-1", text="公表", visibility="public")])

    assert _model(doc)["coverage"]["public_as_is_without_verification"] == ["as-1"]


def test_coverage_excludes_public_as_is_marked_reality_checked():
    """突合したが乖離が無かった場合、Gapは作られないため永久に未突合と誤検出される。"""
    doc = _doc(as_is=[AsIs(id="as-1", text="公表", visibility="public", reality_checked=True)])

    assert _model(doc)["coverage"]["public_as_is_without_verification"] == []


def test_coverage_excludes_public_as_is_referenced_by_perception_gap():
    doc = _doc(
        as_is=[AsIs(id="as-1", text="公表", visibility="public"),
               AsIs(id="as-2", text="実態", visibility="internal")],
        gaps=[Gap(id="gap-1", text="乖離", kind="perception", from_as_is=["as-1", "as-2"])],
    )

    assert _model(doc)["coverage"]["public_as_is_without_verification"] == []


def test_coverage_excludes_challenge_confirmed_as_not_attempted():
    """「取り組んでいない」という確認済みの事実は、未確認の空欄とは違う。"""
    doc = _doc(
        challenges=[Challenge(id="ch-1", text="後戻り")],
        attempts=[Attempt(id="at-1", description="未着手", outcome="not_attempted",
                          challenge_ids=["ch-1"])],
    )

    assert _model(doc)["coverage"]["challenges_without_attempt"] == []


def test_bottleneck_count_reflects_confirmed_only():
    doc = _doc(bottlenecks=[Bottleneck(id="bn-1", text="承認3階層", confidence="confirmed")])

    assert _model(doc)["structure"]["bottlenecks"] == {"count": 1, "confirmed": 1}


def test_stakeholder_structure_is_counted_without_scope():
    doc = _doc(stakeholders=[Stakeholder(id="sh-1", text="部長", confidence="confirmed")])

    assert _model(doc)["structure"]["stakeholders"] == {"count": 1, "confirmed": 1}


def _target(version=1, report="as-is-report-v1") -> ConvergenceTarget:
    return ConvergenceTarget(requirements_version=version, as_is_report_id=report)


def _all_checks(state="completed") -> dict:
    from medo_core.checks import CHECK_REGISTRY
    return {name: CheckState(state=state, event_id="ev-1") for name in CHECK_REGISTRY}


def _grounded_doc() -> RequirementsDoc:
    return _doc(
        as_is=[AsIs(id="as-1", text="実態", visibility="internal", confidence="confirmed")],
        to_be=[ToBe(id="tb-1", text="自動化", confidence="confirmed")],
        gaps=[Gap(id="gap-1", text="乖離", kind="goal",
                  from_as_is=["as-1"], from_to_be=["tb-1"])],
        stakeholders=[Stakeholder(id="sh-1", text="部長", is_decision_maker=True)],
    )


def _go_ahead() -> list[EffectiveResponse]:
    return [EffectiveResponse(stakeholder_id="sh-1", purpose="to_be_go_ahead",
                              reaction="agreed", event_id="ev-9")]


def _codes(result: dict) -> list[str]:
    return [c["code"] for c in result["failed_conditions"]]


def test_readiness_is_not_evaluable_in_discovery_phase():
    result = readiness(_doc(), _target(), _all_checks(), [], review_findings=[])

    assert result["state"] == "not_evaluable"


def test_readiness_reports_missing_internal_as_is():
    doc = _doc(to_be=[ToBe(id="tb-1", text="自動化")])

    assert "internal_as_is_missing" in _codes(
        readiness(doc, _target(), _all_checks(), [], review_findings=[])
    )


def test_readiness_reports_confirmed_to_be_without_grounding():
    """公開情報だけのAsIsから確定したToBeは理想の正論に終わる。"""
    doc = _doc(
        as_is=[AsIs(id="as-1", text="実態", visibility="internal", confidence="confirmed")],
        to_be=[ToBe(id="tb-1", text="自動化", confidence="confirmed")],
    )

    assert "unsupported_confirmed_to_be" in _codes(
        readiness(doc, _target(), _all_checks(), [], review_findings=[])
    )


def test_readiness_accepts_to_be_grounded_through_goal_gap():
    result = readiness(_grounded_doc(), _target(), _all_checks(), _go_ahead(),
                       review_findings=[])

    assert "unsupported_confirmed_to_be" not in _codes(result)


def test_readiness_reports_unrecorded_checks():
    checks = _all_checks()
    checks["reality_gap"] = CheckState()

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert {"code": "check_missing", "refs": ["reality_gap"]} in result["failed_conditions"]


def test_undeterminable_with_open_disposition_blocks_convergence():
    """すべてを undeterminable と記録すれば収束できる抜け道を塞ぐ。"""
    checks = _all_checks()
    checks["to_be_articulation"] = CheckState(state="undeterminable", disposition="open")

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert {"code": "undeterminable_open", "refs": ["to_be_articulation"]} in \
        result["failed_conditions"]


def test_undeterminable_with_disposition_decided_does_not_block():
    checks = _all_checks()
    checks["to_be_articulation"] = CheckState(state="undeterminable", disposition="deferred")

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert result["state"] == "ready"


def test_reality_gap_cannot_be_deferred_only_promoted():
    """判断できないまま先へ進むと提案の土台が崩れる2項目は保留を許さない。"""
    checks = _all_checks()
    checks["reality_gap"] = CheckState(state="undeterminable", disposition="deferred")

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert "undeterminable_open" in _codes(result)


def test_reality_gap_promoted_unblocks_convergence():
    checks = _all_checks()
    checks["reality_gap"] = CheckState(state="undeterminable", disposition="promoted")

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert result["state"] == "ready"


def test_readiness_reports_missing_report_for_current_version():
    result = readiness(_grounded_doc(), ConvergenceTarget(requirements_version=1),
                       _all_checks(), _go_ahead(), review_findings=[])

    assert "as_is_report_missing" in _codes(result)


def test_readiness_requires_go_ahead_not_phase_signoff():
    """この段階では打ち手も費用感も提示していない。フェーズ完了承認は求めない。"""
    result = readiness(_grounded_doc(), _target(), _all_checks(), [], review_findings=[])

    assert "to_be_go_ahead_missing" in _codes(result)
    assert "decision_maker_signoff_missing" not in _codes(result)


def test_readiness_reports_open_objection_of_high_influence_stakeholder():
    doc = _grounded_doc()
    doc.stakeholders.append(Stakeholder(id="sh-2", text="情シス部長", influence="high"))
    responses = _go_ahead() + [EffectiveResponse(
        stakeholder_id="sh-2", purpose="as_is_alignment", reaction="objected",
        event_id="ev-7")]

    result = readiness(doc, _target(), _all_checks(), responses, review_findings=[])

    assert {"code": "high_influence_objection_open", "refs": ["ev-7"]} in \
        result["failed_conditions"]


def test_subsumed_objection_does_not_block():
    doc = _grounded_doc()
    doc.stakeholders.append(Stakeholder(id="sh-2", text="情シス部長", influence="high"))
    responses = _go_ahead() + [EffectiveResponse(
        stakeholder_id="sh-2", purpose="as_is_alignment", reaction="objected",
        event_id="ev-7", subsumed_by="ev-8")]

    result = readiness(doc, _target(), _all_checks(), responses, review_findings=[])

    assert "high_influence_objection_open" not in _codes(result)


def test_phase_readiness_is_not_evaluable_without_prfaq():
    result = phase_readiness("ready", artifacts={}, freshness={}, responses=[],
                             target=_target(), decision_makers=set())

    assert result["state"] == "not_evaluable"


def test_round_delta_counts_undeterminable_only_on_first_detection():
    """毎周「やはり判断できません」で progress_count が非ゼロになると
    進捗のない空転が発散警告に引っかからなくなる。"""
    from medo_core.events import CheckRecorded, RequirementsTarget

    def _ev(ev_id, round_id):
        ev = CheckRecorded(
            target=RequirementsTarget(version=1), occurred_on="2026-08-30",
            requirements_version=1, round_id=round_id,
            check="to_be_articulation", result="undeterminable", note="未定",
        )
        return ev.model_copy(update={"id": ev_id})

    events = [_ev("ev-1", 1), _ev("ev-2", 2)]

    assert round_delta(None, _doc(), events, round_id=1)["undeterminable_found"] == \
        ["to_be_articulation"]
    assert round_delta(None, _doc(), events, round_id=2)["undeterminable_found"] == []


def _final_slides():
    from medo_core.artifacts import Artifact, Freshness

    artifacts = {
        "prfaq-v1": Artifact(project="p1", type="prfaq", requirements_version=1,
                             grown_from=GrownFrom(artifact="mini-prfaq-v1", option="A案"),
                             generated_by="claude", content="x"),
        "slides-v1": Artifact(project="p1", type="slides", slide_kind="final",
                              requirements_version=1, generated_by="claude", content="x"),
    }
    freshness = {a: Freshness(state="current") for a in artifacts}
    target = ConvergenceTarget(requirements_version=1, as_is_report_id="as-is-report-v1",
                               final_slides_id="slides-v1")
    return artifacts, freshness, target


def _signoff(stakeholder_id, *, on_current=True):
    return EffectiveResponse(stakeholder_id=stakeholder_id, purpose="phase_signoff",
                             reaction="agreed", event_id="ev-9",
                             on_current_target=on_current)


def test_phase_signoff_from_a_non_decision_maker_does_not_pass():
    """頭数では判定しない。現場担当の承認でフェーズを閉じさせない。"""
    artifacts, freshness, target = _final_slides()

    result = phase_readiness("ready", artifacts, freshness, [_signoff("sh-2")],
                             target, decision_makers={"sh-1"})

    assert "phase_signoff_missing" in [c["code"] for c in result["failed_conditions"]]


def test_phase_signoff_from_the_decision_maker_passes():
    artifacts, freshness, target = _final_slides()

    result = phase_readiness("ready", artifacts, freshness, [_signoff("sh-1")],
                             target, decision_makers={"sh-1"})

    assert result["state"] == "ready"


def test_signoff_on_superseded_slides_does_not_pass():
    """資料を作り直したら、旧資料への承認は同じ承認とは言えない。"""
    artifacts, freshness, target = _final_slides()

    result = phase_readiness("ready", artifacts, freshness,
                             [_signoff("sh-1", on_current=False)],
                             target, decision_makers={"sh-1"})

    assert "phase_signoff_missing" in [c["code"] for c in result["failed_conditions"]]
