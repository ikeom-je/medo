import pytest

from medo_core.research import Candidate, PROFILES, STOP_CONDITIONS, Verdict, research_plan, triage


def _candidate(url: str, **changes) -> Candidate:
    return Candidate(url=url, **changes)


def _verdict(url: str, **changes) -> Verdict:
    return Verdict(
        url=url,
        relevance=changes.pop("relevance", 0.5),
        aspect=changes.pop("aspect", "market"),
        is_primary=changes.pop("is_primary", 0.5),
        worth_descending=changes.pop("worth_descending", 0.5),
        **changes,
    )


def test_default_profile_is_structural_with_three_hops_and_twenty_pages():
    profile = PROFILES["structural"]

    assert profile.max_hops == 3
    assert profile.max_pages == 20


def test_primary_weight_rises_with_depth():
    """深いほど一次資料を上に置く。表面情報の排除はここで効く。"""
    assert (
        PROFILES["scan"].primary_weight
        < PROFILES["structural"].primary_weight
        < PROFILES["deep"].primary_weight
    )

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


def test_triage_rejects_candidates_beyond_the_profile_hop_limit():
    result = triage(
        [_candidate("https://example.com/deep", hop=4)],
        [_verdict("https://example.com/deep")],
        "structural",
    )

    assert result["open"] == []
    assert result["rejected"] == [{"url": "https://example.com/deep", "reason": "too_deep"}]


def test_triage_rejects_candidates_outside_the_research_aspects():
    result = triage(
        [_candidate("https://example.com/irrelevant")],
        [_verdict("https://example.com/irrelevant", aspect="none")],
        "structural",
    )

    assert result["open"] == []
    assert result["rejected"] == [{"url": "https://example.com/irrelevant", "reason": "off_aspect"}]


def test_triage_prefers_primary_sources_for_the_deep_profile():
    result = triage(
        [_candidate("https://example.com/relevant"), _candidate("https://example.com/primary")],
        [
            _verdict("https://example.com/relevant", relevance=0.9, is_primary=0.1),
            _verdict("https://example.com/primary", relevance=0.2, is_primary=0.9),
        ],
        "deep",
    )

    assert result["open"] == ["https://example.com/primary", "https://example.com/relevant"]


def test_triage_rejects_candidates_that_exceed_the_remaining_page_budget():
    candidates = [_candidate(f"https://example.com/{number}") for number in range(6)]
    verdicts = [
        _verdict(candidate.url, relevance=1 - number / 10)
        for number, candidate in enumerate(candidates)
    ]

    result = triage(candidates, verdicts, "scan")

    assert result["open"] == [candidate.url for candidate in candidates[:5]]
    assert result["rejected"] == [{"url": candidates[5].url, "reason": "budget"}]
    assert result["budget_left"] == 0


def test_triage_stops_when_no_remaining_candidate_is_worth_descending_into():
    result = triage(
        [_candidate("https://example.com/a"), _candidate("https://example.com/b")],
        [
            _verdict("https://example.com/a", worth_descending=0.29),
            _verdict("https://example.com/b", worth_descending=0.1),
        ],
        "structural",
    )

    assert result["diminishing_returns"] is True


def test_a_primary_source_outranks_a_surface_article_at_the_default_depth():
    """実測: 公的資料は案件固有の語を含まずrelevanceが低く出る(0.29 対 0.38)。

    relevance だけで並べると入門まとめ記事が一次資料に勝ってしまう。
    """
    candidates = [
        Candidate(url="https://matome.example.com/a", hop=1),
        Candidate(url="https://www.meti.go.jp/a", hop=1),
    ]
    verdicts = [
        Verdict(url="https://matome.example.com/a", relevance=0.38, aspect="market",
                is_primary=0.08, worth_descending=0.64),
        Verdict(url="https://www.meti.go.jp/a", relevance=0.29, aspect="policy",
                is_primary=0.87, worth_descending=0.72),
    ]

    assert triage(candidates, verdicts, "structural")["open"][0] == "https://www.meti.go.jp/a"
