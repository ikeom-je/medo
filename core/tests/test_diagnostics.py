from medo_core.diagnostics import diagnostic_phase, model_diagnostics
from medo_core.nodes import (
    AsIs, Attempt, Bottleneck, Challenge, Gap, Hypothesis, Kpi, PromotionSource,
    Stakeholder, ToBe,
)
from medo_core.requirements import RequirementsDoc


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
