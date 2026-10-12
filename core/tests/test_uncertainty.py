import pytest

from medo_core.fermi import FermiModel, FermiVar
from medo_core.nodes import FermiRef, Hypothesis
from medo_core.uncertainty import (
    Strategy, candidate_pairs, rank, reach, search_grid, sensitivity, switch_points, value_at,
)


def _s(name, formula, x=1.0, unit="万円", tier="main"):
    model = FermiModel(name=name, unit=unit, formula=formula,
                       variables={"x": FermiVar(assume=x), "k": FermiVar(assume=2.0)})
    return Strategy(name=name, tier=tier, model=model, variable="x")


def test_grid_positive_is_log_spanning_tenfold():
    g = search_grid([1.0, 4.0], None)
    assert len(g) == 200 and g[0] == pytest.approx(0.1) and g[-1] == pytest.approx(40.0)
    assert g[1] / g[0] == pytest.approx(g[2] / g[1])


def test_grid_with_zero_or_negative_is_linear():
    g = search_grid([-1.0, 3.0], None)
    assert g[0] == pytest.approx(-5.0) and g[-1] == pytest.approx(7.0)
    assert g[1] - g[0] == pytest.approx(g[2] - g[1])


def test_grid_explicit_range_log_if_positive_else_linear():
    assert search_grid([5.0], (0.01, 1.0))[0] == pytest.approx(0.01)
    lin = search_grid([5.0], (0.0, 1.0))
    assert lin[1] - lin[0] == pytest.approx(lin[2] - lin[1])


def test_sensitivity_ratio_none_when_base_zero():
    s = _s("A", "x - 1", x=1.0)
    out = sensitivity(s, {}, search_grid([1.0], None))
    assert out["base"] == 0 and out["ratio"] is None and out["swing"] > 0


def test_sensitivity_uses_abs_base():
    s = _s("A", "0 - x * k", x=1.0)
    out = sensitivity(s, {}, search_grid([1.0], None))
    assert out["ratio"] > 0


@pytest.mark.parametrize("assumed, expected", [
    ([0.0], (-1.0, 1.0)), ([-0.2], (-0.4, 0.0)), ([-2.0], (-4.0, 0.0)),
])
def test_grid_equal_nonpositive_assumptions_use_absolute_value_or_one(assumed, expected):
    grid = search_grid(assumed, None)
    assert (grid[0], grid[-1]) == pytest.approx(expected)


@pytest.mark.parametrize("formula", ["x / 0", "x + missing", "x +", "x ** 1000",
                                    "1e308 * x", "(0 - x) ** 0.5"])
def test_value_at_returns_none_for_failed_or_nonreal_calculations(formula):
    assert value_at(_s("A", formula), {}, 2.0) is None


@pytest.mark.parametrize("variable", ["missing", "fact_variable"])
def test_value_at_does_not_create_variables_or_replace_facts(variable):
    s = _s("A", "x")
    s.model.variables["fact_variable"] = FermiVar(fact="fact-1")
    s.variable = variable
    assert value_at(s, {}, 2.0) is None


def test_value_at_keeps_other_assumptions_and_original_model():
    s = _s("A", "x * k")
    assert value_at(s, {}, 3.0) == 6.0
    assert s.model.variables["x"].assume == 1.0
    assert s.model.variables["k"].assume == 2.0


def test_switch_between_two_linear_strategies():
    a, b = _s("A", "x * 10", x=1.0), _s("B", "20 + x * 0", x=1.0, tier="sub")
    out = switch_points([a, b], {}, search_grid([1.0], (0.0, 5.0)))
    assert len(out["points"]) == 1
    p = out["points"][0]
    assert p["at"] == pytest.approx(2.0, rel=1e-2) and (p["from"], p["to"]) == ("B", "A")


def test_switch_ignores_crossing_below_top():
    a = _s("A", "0 - x", x=1.0)
    b = _s("B", "0.1 + x * 0", x=1.0, tier="sub")
    c = _s("C", "x", x=1.0, tier="sub")
    out = switch_points([a, b, c], {}, search_grid([1.0], (-1.0, 1.0)))
    assert [(p["from"], p["to"]) for p in out["points"]] == [("A", "B"), ("B", "C")]
    assert [p["at"] for p in out["points"]] == [pytest.approx(-0.1, rel=1e-2),
                                                 pytest.approx(0.1, rel=1e-2)]


def test_switch_reports_discontinuity():
    a = _s("A", "1 / (x - 1)", x=2.0)
    b = _s("B", "0 + x * 0", x=2.0, tier="sub")
    out = switch_points([a, b], {}, search_grid([2.0], (0.0, 3.0)))
    assert any(abs(d["near"] - 1.0) < 0.05 for d in out["discontinuities"])
    assert all(abs(p["at"] - 1.0) > 0.05 for p in out["points"])


def test_switch_no_change_reports_always_top_as_approximation():
    a, b = _s("A", "x + 10", x=1.0), _s("B", "x", x=1.0, tier="sub")
    out = switch_points([a, b], {}, search_grid([1.0], None))
    assert out["points"] == [] and out["always_top"] == "A"


def test_switch_requires_same_nonempty_unit():
    a, b = _s("A", "x", unit="万円"), _s("B", "x", unit="件", tier="sub")
    assert "unit" in switch_points([a, b], {}, search_grid([1.0], None))["error"]


def test_switch_fails_whole_comparison_when_one_strategy_never_evaluates():
    a = _s("A", "x")
    b = _s("B", "x / 0", tier="sub")
    out = switch_points([a, b], {}, search_grid([1.0], None))
    assert out["error"] and out["points"] == []


def test_switch_for_nonmonotonic_formula_finds_both_boundaries():
    out = switch_points([_s("A", "x ** 2", x=2.0), _s("B", "1", tier="sub")],
                        {}, search_grid([2.0], (-2.0, 2.0)))
    assert [p["at"] for p in out["points"]] == pytest.approx([-1.0, 1.0], rel=1e-2)
    assert [(p["from"], p["to"]) for p in out["points"]] == [("A", "B"), ("B", "A")]


def test_switch_close_crossings_between_grid_points_remain_approximate():
    out = switch_points([_s("A", "1 - (x - 1.001) * (x - 1.002)"),
                         _s("B", "1", tier="sub")], {}, [0.0, 0.5, 1.0, 1.5, 2.0])
    assert out["points"] == [] and out["always_top"] == "B"


def test_switch_excludes_failed_grid_points_without_bridging_them():
    out = switch_points([_s("A", "1 / (x - 1)", x=2.0),
                         _s("B", "0", x=2.0, tier="sub")], {}, [0.0, 1.0, 2.0])
    assert out["excluded"] == [1.0]
    assert out["points"] == [] and out["discontinuities"] == []
    assert out["always_top"] is None


def test_switch_failed_refinement_is_undetermined_not_always_top():
    out = switch_points([_s("A", "1 / (x - 1)", x=2.0),
                         _s("B", "0", x=2.0, tier="sub")], {}, [0.0, 2.0])
    assert out["undetermined"] == [1.0]
    assert out["points"] == [] and out["discontinuities"] == []
    assert out["always_top"] is None


def test_switch_requires_nonempty_unit():
    assert "unit" in switch_points([_s("A", "x", unit=""), _s("B", "1", unit="")],
                                    {}, [0.0, 2.0])["error"]


def test_switch_single_option_returns_comparison_reason():
    out = switch_points([_s("A", "x")], {}, [0.0, 2.0])
    assert "策が1つ" in out["error"] and out["points"] == []


def test_switch_invalid_base_prevents_comparison_even_if_grid_evaluates():
    out = switch_points([_s("A", "1 / (x - 1)", x=1.0),
                         _s("B", "0", tier="sub")], {}, [0.0, 2.0])
    assert out["error"] and out["points"] == []


def test_switch_no_evaluable_points_returns_error_and_excluded_points():
    out = switch_points([_s("A", "x"), _s("B", "x / 0", tier="sub")], {}, [0.0, 2.0])
    assert out["error"] and out["points"] == []
    assert out["excluded"] == [0.0, 2.0]


def test_reach_counts_determines_only_and_collapses_cycles():
    edges = [("h1", "h2", "determines"), ("h2", "h1", "determines"),
             ("h2", "h3", "determines"), ("h1", "h4", "narrows")]
    r = reach(["h1", "h2", "h3", "h4"], edges)
    assert r["h1"]["determines"] == 2
    assert r["h1"]["narrows"] == 1 and r["h3"]["determines"] == 0


def test_rank_order():
    items = [
        {"id": "hyp-3", "kind": "hyp", "switch": False, "reach": 5, "swing_ratio": 2.0,
         "decision_relevant": 0.9, "effort": "ask"},
        {"id": "hyp-1", "kind": "hyp", "switch": True, "reach": 0, "swing_ratio": 0.1,
         "decision_relevant": None, "effort": "experiment"},
        {"id": "oq-1", "kind": "oq", "switch": False, "reach": "not_applicable",
         "swing_ratio": None, "decision_relevant": 0.9, "effort": "ask"},
        {"id": "hyp-2", "kind": "hyp", "switch": False, "reach": "unknown", "swing_ratio": None,
         "decision_relevant": None, "effort": None},
    ]
    assert [i["id"] for i in rank(items)] == ["hyp-1", "hyp-3", "oq-1", "hyp-2"]


def test_candidate_pairs_by_shared_fermi_or_challenge():
    h = [Hypothesis(id="hyp-1", kind="impact", statement="a", challenge_ids=["ch-1"]),
         Hypothesis(id="hyp-2", kind="impact", statement="b", challenge_ids=["ch-1"]),
         Hypothesis(id="hyp-3", kind="impact", statement="c", challenge_ids=["ch-9"],
                    status="validated")]
    assert set(candidate_pairs(h)) == {("hyp-1", "hyp-2"), ("hyp-2", "hyp-1")}


def test_candidate_pairs_use_shared_fermi_even_with_different_variables():
    hypotheses = [
        Hypothesis(id="hyp-1", kind="impact", statement="a",
                   fermi_ref=FermiRef(artifact_id="fermi-v1", variable_name="x")),
        Hypothesis(id="hyp-2", kind="cause", statement="b", status="validating",
                   fermi_ref=FermiRef(artifact_id="fermi-v1", variable_name="k")),
        Hypothesis(id="hyp-3", kind="impact", statement="c",
                   fermi_ref=FermiRef(artifact_id="fermi-v2", variable_name="x")),
        Hypothesis(id="hyp-4", kind="impact", statement="d", status="rejected",
                   fermi_ref=FermiRef(artifact_id="fermi-v1", variable_name="x")),
    ]
    assert candidate_pairs(hypotheses) == [("hyp-1", "hyp-2"), ("hyp-2", "hyp-1")]


def test_candidate_pairs_without_links_are_empty():
    assert candidate_pairs([Hypothesis(id=f"hyp-{n}", kind="impact", statement="a")
                            for n in range(1, 4)]) == []


def test_reach_counts_distinct_nodes_in_diamonds_and_only_direct_narrows():
    edges = [("h1", "h2", "determines"), ("h1", "h3", "determines"),
             ("h2", "h4", "determines"), ("h3", "h4", "determines"),
             ("h1", "h5", "narrows"), ("h5", "h6", "narrows"),
             ("h1", "h5", "narrows")]
    out = reach([f"h{i}" for i in range(1, 7)], edges)
    assert out["h1"] == {"determines": 3, "narrows": 1}
    assert out["h5"] == {"determines": 0, "narrows": 1}


def test_reach_cycles_with_shared_descendants_exclude_self():
    edges = [("h1", "h2", "determines"), ("h2", "h1", "determines"),
             ("h2", "h3", "determines"), ("h3", "h4", "determines"),
             ("h4", "h3", "determines"), ("h4", "h5", "determines"),
             ("h1", "h1", "determines")]
    out = reach([f"h{i}" for i in range(1, 7)], edges)
    assert out["h1"]["determines"] == out["h2"]["determines"] == 4
    assert out["h3"]["determines"] == out["h4"]["determines"] == 2
    assert out["h5"]["determines"] == out["h6"]["determines"] == 0


@pytest.mark.parametrize("first, second", [
    ({"switch": True}, {"reach": 100}),
    ({"reach": 1}, {"swing_ratio": 100.0}),
    ({"reach": 0}, {"reach": "unknown", "swing_ratio": 100.0}),
    ({"reach": 0}, {"reach": "not_applicable", "swing_ratio": 100.0}),
    ({"swing_ratio": 1.0}, {"decision_relevant": 1.0}),
    ({"swing_ratio": 0.0}, {"swing_ratio": None, "decision_relevant": 1.0}),
    ({"decision_relevant": 0.5, "effort": "experiment"}, {"decision_relevant": 0.49}),
    ({"effort": "ask"}, {"effort": "research"}),
    ({"effort": "research"}, {"effort": "experiment"}),
    ({"effort": "experiment"}, {"effort": None}),
])
def test_rank_respects_each_priority_before_later_fields(first, second):
    base = {"kind": "hyp", "switch": False, "reach": 0, "swing_ratio": None,
            "decision_relevant": None, "effort": "ask"}
    items = [{**base, "id": "hyp-2", **first}, {**base, "id": "hyp-1", **second}]
    assert [i["id"] for i in rank(items)] == ["hyp-2", "hyp-1"]


def test_rank_ties_use_kind_and_numeric_id_without_changing_unknown_reach():
    base = {"switch": False, "swing_ratio": None, "decision_relevant": None, "effort": None}
    items = [{**base, "kind": kind, "id": id_, "reach": value} for kind, id_, value in [
        ("oq", "oq-2", "not_applicable"), ("hyp", "hyp-10", "unknown"),
        ("oq", "oq-1", "not_applicable"), ("hyp", "hyp-2", "unknown")]]
    assert [i["id"] for i in rank(items)] == ["hyp-2", "hyp-10", "oq-1", "oq-2"]
    assert items[0]["id"] == "oq-2" and items[1]["reach"] == "unknown"


def test_switch_across_excluded_points_is_undetermined():
    # x=1 付近は A が計算できない。その前後で最上位が B から A に入れ替わる
    a = _s("A", "x * 10 + 0 / (x - 1) * 0", x=2.0)
    b = _s("B", "11 + x * 0", x=2.0, tier="sub")
    grid = [0.5, 0.9, 1.0, 1.1, 1.5]
    out = switch_points([a, b], {}, grid)
    assert 1.0 in out["excluded"]
    assert out["undetermined"] and out["always_top"] is None
