import pytest

from medo_core.research import PROFILES, STOP_CONDITIONS, research_plan


def test_default_profile_is_structural_with_three_hops_and_twenty_pages():
    profile = PROFILES["structural"]

    assert profile.max_hops == 3
    assert profile.max_pages == 20


def test_scan_does_not_prefer_primary_sources_but_deep_does():
    assert PROFILES["scan"].prefer_primary is False
    assert PROFILES["deep"].prefer_primary is True


def test_stop_conditions_do_not_include_filled_aspects():
    assert all("観点が埋まった" not in condition for condition in STOP_CONDITIONS)


def test_plan_has_no_findings_to_resolve_when_open_findings_are_empty():
    plan = research_plan("structural", {"links": {}, "coverage": {}})

    assert plan["findings_to_resolve"] == {"links": {}, "coverage": {}}


def test_plan_targets_only_nonempty_link_and_coverage_findings():
    plan = research_plan(
        "structural",
        {
            "links": {
                "challenges_without_cause": ["ch-1"],
                "to_be_without_kpi": [],
            },
            "coverage": {
                "public_as_is_without_verification": ["as-1"],
                "challenges_without_attempt": [],
            },
        },
    )

    assert plan["findings_to_resolve"] == {
        "links": {"challenges_without_cause": [{"id": "ch-1", "text": ""}]},
        "coverage": {"public_as_is_without_verification": [{"id": "as-1", "text": ""}]},
    }


def test_findings_carry_the_node_text_so_the_target_is_actionable():
    """IDだけでは何を調べるか決められない。"""
    plan = research_plan(
        "structural",
        {"links": {"challenges_without_cause": ["ch-1"]}, "coverage": {}},
        {"ch-1": "計画作成に3日かかる"},
    )

    assert plan["findings_to_resolve"]["links"]["challenges_without_cause"] == [
        {"id": "ch-1", "text": "計画作成に3日かかる"}
    ]


def test_deep_reaches_primary_sources_behind_several_hops():
    """一次資料はポータル→検索→一覧→詳細→PDFと辿るため3階層では届かない。"""
    assert PROFILES["deep"].max_hops > PROFILES["structural"].max_hops


def test_unknown_profile_name_raises_value_error():
    with pytest.raises(ValueError, match="未知の深度プロファイル"):
        research_plan("unknown", {})
