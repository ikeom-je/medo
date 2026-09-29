import pytest

from medo_core.source_check import check, extract_numbers, nearby_excerpt, quote_in_body, value_matches


@pytest.mark.parametrize(
    ("quote", "value", "unit", "expected"),
    [
        ("市場規模は3.2兆円", 3.2, "兆円", True),
        ("3,215,000百万円", 3.215, "兆円", True),
        ("3,215,000百万円", 3.2, "兆円", False),
        ("3兆2,000億円", 3.2, "兆円", True),
        ("市場規模は3.3兆円", 3.2, "兆円", False),
        ("3.2兆円", 32, "兆円", False),
        ("約3.2兆円程度", 3.2, "兆円", True),
        ("前年比12.5%増", 12.5, "%", True),
        ("▲5.2%", -5.2, "%", True),
        ("▲5.2%", 5.2, "%", False),
        ("3.2兆人", 3.2, "兆円", False),
        ("(単位:百万円)3,215,000", 3215000, "百万円", True),
        ("(単位:万人)3,215,000", 3215000, "百万円", False),
        ("(単位:万人)3,215,000 (単位:百万円)42", 3215000, "百万円", False),
        ("2024  3.2", 3.2, "兆円", False),
    ],
)
def test_spec_number_matches(quote, value, unit, expected):
    assert value_matches(quote, value, unit) is expected


def test_quote_matching_uses_nfkc_and_ignores_whitespace():
    assert quote_in_body("３．２ 兆円", "市場は3.2\n兆円です")
    assert not quote_in_body("3.3兆円", "市場は3.2兆円です")


def test_number_extraction_preserves_boundaries_and_sign():
    numbers = extract_numbers("2024  3兆2,000億円 ▲5.2% マイナス3万人")
    assert [number.value for number in numbers] == [2024, 3.2e12, -5.2, -30000]
    assert numbers[1].suffix == "円"


def test_check_reports_rejection_and_nearby_excerpt():
    result = check("市場は3.2兆円", "昨年の市場は3.3兆円でした", 3.2, "兆円")
    assert result.reason == "quote-not-found"
    assert "市場は3.3兆円" in result.nearby
    assert nearby_excerpt("別の記述 3.2兆円", "数値3.2兆円がありました", 3.2, "兆円")
    assert check("3.2兆円", "3.2兆円", 3.3, "兆円").reason == "value-not-in-quote"
    assert check("定性的な記述", "定性的な記述", None, "").verified


def test_unit_annotation_in_parentheses_is_ignored_for_matching():
    assert value_matches("F1 scores by up to 43.67%.", 43.67, "%(F1向上率)")
    assert value_matches("(単位:百万円)3,215,000", 3215000, "百万円（売上高）")
    assert not value_matches("F1 scores by up to 43.67%.", 43.6, "%(F1向上率)")
