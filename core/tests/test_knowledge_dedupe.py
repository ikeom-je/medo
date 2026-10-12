from datetime import date

import pytest

from medo_core.artifacts import Artifact, ArtifactStore, GrownFrom, OptionMeta
from medo_core.knowledge import KnowledgeEntry, KnowledgeStore
from medo_core.knowledge_dedupe import (
    PairJudgment,
    Routing,
    affected_artifacts,
    candidate_pairs,
    check_components,
    route,
)
from medo_core.storage import LocalJsonStorage


def _e(i, **kw):
    base = dict(entry_id=f"tech-{i}", kind="tech", statement="s", source=f"https://e.com/{i}",
                retrieved="2026-09-01")
    return KnowledgeEntry(**{**base, **kw})


def _j(relation, rc=0.9, scope=0.9, newer="same", nc=0.9, keep="a", kc=0.9):
    return PairJudgment(relation=relation, relation_confidence=rc, same_scope=scope,
                        newer=newer, newer_confidence=nc, keep=keep, keep_confidence=kc)


def test_candidate_pairs_by_same_url_ignoring_arxiv_abs_pdf():
    a = _e(1, source="https://arxiv.org/abs/2311.17311", statement="USC は精度を上げる")
    b = _e(2, source="https://arxiv.org/pdf/2311.17311", statement="全く別の言い回し")
    c = _e(3, source="https://other.example/x", statement="無関係な話題")
    assert candidate_pairs([a, b, c]) == [("tech-1", "tech-2")]


def test_candidate_pairs_by_char_bigram_overlap():
    a = _e(1, statement="市場規模は2024年に3.2兆円")
    b = _e(2, statement="2024年の市場規模は3.2兆円だった", source="https://x.example/y")
    assert ("tech-1", "tech-2") in candidate_pairs([a, b])


def test_candidate_pairs_ignore_query_extension_and_trailing_slash():
    a = _e(1, source="https://EXAMPLE.com/report.pdf?x=1")
    b = _e(2, source="http://example.com/report.html/?x=2")
    assert candidate_pairs([a, b]) == [("tech-1", "tech-2")]


def test_candidate_pairs_use_units_without_annotations():
    assert candidate_pairs([_e(1, unit="兆円(国内)"), _e(2, unit="兆円（海外）")]) == [
        ("tech-1", "tech-2")]


def test_candidate_pairs_normalize_nfkc_and_whitespace():
    assert candidate_pairs([_e(1, statement="Ａ Ｂ Ｃ"), _e(2, statement="ABC")]) == [
        ("tech-1", "tech-2")]


def test_candidate_pairs_are_sorted_by_number_and_only_include_live_same_kind():
    entries = [
        _e(10, unit="%"), _e(2, unit="%"), _e(1, unit="%"),
        _e(3, unit="%", superseded_by="tech-10", supersede_reason="duplicate",
           superseded_on="2026-10-04"),
        _e(4, kind="market", entry_id="market-4", unit="%"),
    ]
    assert candidate_pairs(entries) == [
        ("tech-1", "tech-2"), ("tech-1", "tech-10"), ("tech-2", "tech-10")]


def test_candidate_pairs_do_not_treat_non_url_sources_as_same_url():
    assert candidate_pairs([
        _e(1, kind="practice", source="対話メモA", statement="abc"),
        _e(2, kind="practice", source="対話メモB", statement="xyz"),
    ]) == []


def test_candidate_pairs_do_not_apply_arxiv_rules_to_other_hosts():
    assert candidate_pairs([
        _e(1, source="https://arxiv.org.evil.example/abs/123"),
        _e(2, source="https://arxiv.org.evil.example/pdf/123"),
    ]) == []


def test_route_conflicting_always_conflict():
    assert route(_e(1), _e(2), _j("conflicting", rc=0.3)).bucket == "conflict"


def test_route_duplicate_with_mismatched_value_is_conflict():
    a, b = _e(1, value=3.2, unit="兆円"), _e(2, value=3.3, unit="兆円")
    assert route(a, b, _j("duplicate")).bucket == "conflict"


def test_route_duplicate_without_values():
    r = route(_e(1), _e(2), _j("duplicate", keep="b"))
    assert (r.bucket, r.old, r.by, r.reason) == ("proposal", "tech-1", "tech-2", "duplicate")


def test_route_rejects_duplicate_with_one_sided_value():
    assert route(_e(1, value=3.2, unit="兆円"), _e(2), _j("duplicate")).bucket in ("requery", "held")
    assert route(_e(1, value=3.2, unit="兆円"), _e(2, unit="兆円"), _j("duplicate")).bucket == "held"


def test_route_duplicate_with_equal_values_and_annotated_units():
    a, b = _e(1, value=0, unit="%（精度）"), _e(2, value=0, unit="%")
    r = route(a, b, _j("duplicate", keep="a"))
    assert (r.bucket, r.old, r.by) == ("proposal", "tech-2", "tech-1")


def test_route_updates_uses_newer_not_retrieved():
    a = _e(1, retrieved="2026-09-30")
    b = _e(2, retrieved="2026-01-01")
    r = route(a, b, _j("updates", newer="b"))
    assert (r.old, r.by, r.reason) == ("tech-1", "tech-2", "updates")


def test_route_low_confidence_requeries_then_holds():
    assert route(_e(1), _e(2), _j("duplicate", scope=0.6)).bucket == "requery"
    assert route(_e(1), _e(2), _j("duplicate", rc=0.4)).bucket == "held"


@pytest.mark.parametrize("judgment", [
    _j("duplicate", rc=0.6), _j("duplicate", nc=0.6), _j("duplicate", kc=0.6),
    _j("updates", scope=0.6), _j("updates", nc=0.6),
])
def test_route_requeries_when_required_judgment_is_uncertain(judgment):
    assert route(_e(1), _e(2), judgment).bucket == "requery"


@pytest.mark.parametrize("relation", ["complementary", "unrelated"])
def test_route_excludes_confident_non_merge_relations(relation):
    assert route(_e(1), _e(2), _j(relation)).bucket == "excluded"
    assert route(_e(1), _e(2), _j(relation, rc=0.6)).bucket == "held"


@pytest.mark.parametrize("judgment", [
    _j("duplicate", newer="a"), _j("duplicate", keep="invalid"),
    _j("updates", newer="unknown"), _j("updates", newer="same"), _j("invalid"),
])
def test_route_holds_when_confident_judgments_do_not_support_merge(judgment):
    assert route(_e(1), _e(2), judgment).bucket == "held"


def test_route_holds_duplicate_with_incompatible_units():
    assert route(_e(1, unit="円"), _e(2, unit="ドル"), _j("duplicate")).bucket == "held"


def test_route_updates_does_not_require_keep_confidence():
    r = route(_e(1), _e(2), _j("updates", newer="a", kc=0.1))
    assert (r.bucket, r.old, r.by) == ("proposal", "tech-2", "tech-1")


def test_route_threshold_boundary():
    j = _j("duplicate", rc=0.8, scope=0.8, nc=0.8, kc=0.8)
    assert route(_e(1), _e(2), j).bucket == "proposal"
    assert route(_e(1), _e(2), j, threshold=0.85).bucket == "requery"


def test_check_components_holds_whole_component_with_conflict():
    p1 = Routing(bucket="proposal", old="tech-1", by="tech-3", reason="duplicate")
    p2 = Routing(bucket="proposal", old="tech-2", by="tech-3", reason="duplicate")
    keep, held = check_components([p1, p2], conflicts=[("tech-1", "tech-2")])
    assert keep == [] and held == [p1, p2]


def test_check_components_holds_branch_and_chain():
    branch = [Routing(bucket="proposal", old="tech-1", by="tech-2", reason="duplicate"),
              Routing(bucket="proposal", old="tech-1", by="tech-3", reason="duplicate")]
    chain = [Routing(bucket="proposal", old="tech-4", by="tech-5", reason="updates"),
             Routing(bucket="proposal", old="tech-5", by="tech-6", reason="updates")]
    keep, held = check_components(branch + chain, conflicts=[])
    assert keep == [] and len(held) == 4


def test_check_components_preserves_input_order_and_valid_components():
    p1 = Routing(bucket="proposal", old="tech-1", by="tech-3", reason="duplicate")
    p2 = Routing(bucket="proposal", old="tech-2", by="tech-3", reason="duplicate")
    p3 = Routing(bucket="proposal", old="tech-4", by="tech-5", reason="updates")
    p4 = Routing(bucket="proposal", old="tech-6", by="tech-7", reason="updates")
    assert check_components([p1, p3, p2, p4], [("tech-2", "tech-1")]) == ([p3, p4], [p1, p2])
    assert check_components([p2, p1], []) == ([p2, p1], [])
    assert check_components([], []) == ([], [])


def _artifact(**kw):
    return Artifact(**{
        "project": "p1", "type": "research", "requirements_version": 1,
        "generated_by": "codex", "content": "調査", **kw,
    })


def test_affected_artifacts_includes_descendants(tmp_path):
    storage = LocalJsonStorage(tmp_path / "data")
    store = ArtifactStore(storage)
    store.save("p1", _artifact(cited_knowledge=["tech-1"]))
    store.save("p1", _artifact(type="as-is-report", derived_from=["research-v1"]))
    rows = affected_artifacts(storage, tmp_path / "knowledge", "tech", "tech-1")
    assert {(r["project"], r["artifact"], r["via"]) for r in rows} == {
        ("p1", "research-v1", "cited"), ("p1", "as-is-report-v1", "research-v1")}


def test_affected_artifacts_with_no_projects_is_empty(tmp_path):
    assert affected_artifacts(
        LocalJsonStorage(tmp_path / "data"), tmp_path / "knowledge", "tech", "tech-1") == []


def test_affected_artifacts_across_projects_excludes_unrelated_stale_artifacts(tmp_path):
    today = date(2026, 10, 4)
    knowledge = KnowledgeStore(tmp_path / "knowledge")
    a, b = (knowledge.save(_e(i, entry_id="", retrieved=today.isoformat())) for i in (1, 2))
    knowledge.supersede("tech", a, b, "updates", today=today)
    storage = LocalJsonStorage(tmp_path / "data")
    store = ArtifactStore(storage)
    store.save("p1", _artifact(cited_knowledge=[a]))
    store.save("p1", _artifact(type="as-is-report", derived_from=["research-v1"]))
    store.save("p1", _artifact(type="slides", slide_kind="discussion",
                               derived_from=["as-is-report-v1"]))
    store.save("p1", _artifact(cited_knowledge=["tech-99"]))
    store.save("p1", _artifact(type="as-is-report", derived_from=["research-v2"]))
    store.save("p2", _artifact(cited_knowledge=[a]))
    storage.put("projects/empty/facts/fact-1", {"x": 1})

    rows = affected_artifacts(storage, tmp_path / "knowledge", "tech", a)

    assert {(r["project"], r["artifact"], r["via"]) for r in rows} == {
        ("p1", "research-v1", "cited"), ("p1", "as-is-report-v1", "research-v1"),
        ("p1", "slides-v1", "as-is-report-v1"), ("p2", "research-v1", "cited")}
    assert store.get("p1", "research-v1").cited_knowledge == [a]


def test_affected_artifacts_does_not_propagate_selection_provenance(tmp_path):
    storage = LocalJsonStorage(tmp_path / "data")
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="mini-prfaq", options=[OptionMeta(name="A")],
                                cited_knowledge=["tech-1"]))
    store.save("p1", _artifact(type="prfaq", grown_from=GrownFrom(artifact="mini-prfaq-v1", option="A")))
    store.save("p1", _artifact(type="slides", slide_kind="final", derived_from=["prfaq-v1"]))

    assert affected_artifacts(storage, tmp_path / "knowledge", "tech", "tech-1") == [
        {"project": "p1", "artifact": "mini-prfaq-v1", "via": "cited"}]
