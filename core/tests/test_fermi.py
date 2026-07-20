import pytest
from medo_core.facts import Fact
from medo_core.fermi import FermiModel, FermiVar, evaluate
from pydantic import ValidationError


def _fact(**kw) -> Fact:
    base = dict(
        fact_id="fact-1",
        kind="market",
        statement="訪日外国人旅行者数",
        value=36870000.0,
        unit="人",
        source="https://www.jnto.go.jp/statistics/",
        retrieved="2026-07-01",
    )
    base.update(kw)
    return Fact(**base)


def test_evaluate_mixes_facts_and_assumptions():
    model = FermiModel(
        name="多言語予約対応の市場機会",
        variables={
            "visitors": FermiVar(fact="fact-1"),
            "dining_rate": FermiVar(assume=0.8, note="外食利用率の仮定"),
            "unit_price": FermiVar(assume=5000.0),
        },
        formula="visitors * dining_rate * unit_price",
    )
    result = evaluate(model, {"fact-1": _fact()})
    assert result.value == 36870000.0 * 0.8 * 5000.0
    assert result.cited_facts == ["fact-1"]
    assert result.resolved["dining_rate"] == 0.8


def test_power_operator_enables_cagr():
    model = FermiModel(
        name="5年後の市場規模",
        variables={"base": FermiVar(assume=100.0), "growth": FermiVar(assume=1.1)},
        formula="base * growth ** 5",
    )
    assert abs(evaluate(model, {}).value - 100.0 * 1.1**5) < 1e-9


def test_undefined_variable_rejected():
    model = FermiModel(name="x", variables={"a": FermiVar(assume=1.0)}, formula="a + b")
    with pytest.raises(ValueError):
        evaluate(model, {})


def test_huge_exponent_rejected():
    model = FermiModel(
        name="x", variables={"a": FermiVar(assume=10.0)}, formula="a ** 1000000"
    )
    with pytest.raises(ValueError):
        evaluate(model, {})


def test_bool_constant_rejected():
    model = FermiModel(name="x", variables={"a": FermiVar(assume=1.0)}, formula="a + True")
    with pytest.raises(ValueError):
        evaluate(model, {})


def test_disallowed_syntax_rejected():
    model = FermiModel(
        name="x", variables={"a": FermiVar(assume=1.0)}, formula="__import__('os').getcwd()"
    )
    with pytest.raises(ValueError):
        evaluate(model, {})


def test_missing_fact_and_missing_value_rejected():
    model = FermiModel(name="x", variables={"a": FermiVar(fact="fact-9")}, formula="a")
    with pytest.raises(ValueError):
        evaluate(model, {})
    with pytest.raises(ValueError):
        evaluate(FermiModel(name="x", variables={"a": FermiVar(fact="fact-1")}, formula="a"),
                 {"fact-1": _fact(value=None)})


def test_var_requires_exactly_one_of_fact_or_assume():
    with pytest.raises(ValidationError):
        FermiVar(fact="fact-1", assume=1.0)
    with pytest.raises(ValidationError):
        FermiVar()
