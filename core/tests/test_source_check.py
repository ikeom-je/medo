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
        ("up to 32 tools", 32, "tools(ツール数)", True),
        ("up to 32 tools", 32, "people", False),
        ("3.2 billion yen", 3.2, "billion yen", True),
        ("3.2 billion yen", 3200, "million yen", True),
        ("3.2 billion yen", 3.2, "million yen", False),
        ("increased by 43.67%.", 43.67, "%(F1向上率)", True),
        ("2024 3.2", 3.2, "兆円", False),
        ("3.2 thousand yen", 3200, "yen", True),
        ("3.2 million yen", 3200000, "yen", True),
        ("3.2 trillion yen", 3.2, "兆yen", True),
        ("3.2 BILLION yen", 3.2, "BiLLion yen", True),
        ("3.2billion yen", 3200, "million yen", True),
        ("-3.2 billion yen", -3200, "million yen", True),
        ("-3.2 billion yen", 3200, "million yen", False),
        ("3.215 billion yen", 3.2, "billion yen", False),
        ("3.2K yen", 3200, "yen", False),
        ("3.2M yen", 3200000, "yen", False),
        ("3.2B yen", 3.2, "billion yen", False),
        ("3 millionaires", 3, "millionaires", True),
        ("32 ツール", 32, "ツール", True),
        ("32 人", 32, "人", True),
        ("12.5 %増", 12.5, "%", True),
        ("(単位:百万円)2024 3.2", 3.2, "百万円", True),
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


@pytest.mark.parametrize(
    ("quote", "value", "multiplier", "suffix"),
    [
        ("up to 32 tools", 32, "", "tools"),
        ("32\ttools available", 32, "", "tools"),
        ("32\nツール利用可能", 32, "", "ツール利用可能"),
        ("32 人", 32, "", "人"),
        ("12.5 %増", 12.5, "", "%増"),
        ("12.5%増 tools", 12.5, "", "%増"),
        ("3.2兆 円", 3.2e12, "兆", "円"),
        ("3.2 thousand yen", 3200, "thousand", "yen"),
        ("3.2 million yen", 3200000, "million", "yen"),
        ("3.2 billion yen", 3.2e9, "billion", "yen"),
        ("3.2 trillion yen", 3.2e12, "trillion", "yen"),
        ("3.2\tBiLLion\nyen", 3.2e9, "billion", "yen"),
        ("3.2billion yen", 3.2e9, "billion", "yen"),
        ("3.2 billion", 3.2e9, "billion", ""),
        ("3 millionaires", 3, "", "millionaires"),
        ("3.2K yen", 3.2, "", "K"),
        ("3.2M yen", 3.2, "", "M"),
        ("3.2B yen", 3.2, "", "B"),
        ("32 , tools", 32, "", ""),
    ],
)
def test_number_extraction_reads_spaced_units_and_english_multipliers(
    quote, value, multiplier, suffix
):
    number, = extract_numbers(quote)
    assert (number.value, number.multiplier, number.suffix) == (value, multiplier, suffix)


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
    assert not value_matches("料金は5円/人", 5, "円/(kWh)(税込)")
    assert not value_matches("5人", 5, "(%)")
