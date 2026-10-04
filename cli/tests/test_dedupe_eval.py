import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest
from medo_core.knowledge import KnowledgeEntry
from medo_core.knowledge_dedupe import PairJudgment, Routing

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def evaluator():
    path = ROOT / "scripts/eval/run_dedupe_eval.py"
    spec = importlib.util.spec_from_file_location("dedupe_eval", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _case(split, label="duplicate", same_source=True):
    def entry(n):
        return KnowledgeEntry(
            entry_id=f"tech-{n}", kind="tech", statement="同じ論文の主張" if same_source else str(n),
            source="https://e.com/paper" if same_source else f"https://e.com/{n}",
            retrieved="2026-09-01",
        ).model_dump(mode="json")

    return {"split": split, "a": entry(1), "b": entry(2), "label": label, "keep": "a"}


def _judgment(relation="duplicate", confidence=0.9):
    return PairJudgment(
        relation=relation, relation_confidence=confidence, same_scope=0.9,
        newer="same", newer_confidence=0.9, keep="a", keep_confidence=0.9,
    )


def test_dedupe_eval_set_has_disjoint_splits_and_all_required_relations():
    cases = json.loads((ROOT / "scripts/eval/dedupe_cases.json").read_text())
    ids = {}
    for split in ("tune", "validate"):
        group = [c for c in cases if c["split"] == split]
        assert len(group) >= 10
        counts = Counter(c["label"] for c in group)
        assert set(counts) == {"duplicate", "updates", "conflicting", "complementary", "unrelated"}
        assert min(counts.values()) >= 2
        entries = [KnowledgeEntry(**c[side]) for c in group for side in ("a", "b")]
        ids[split] = {e.entry_id for e in entries}
        assert len(ids[split]) == len(entries)
        assert any(
            c["label"] == "duplicate" and "arxiv.org/abs/" in c["a"]["source"]
            and "arxiv.org/pdf/" in c["b"]["source"] for c in group
        )
        assert any(
            c["label"] == "updates" and "2023" in c["a"]["statement"]
            and "2025" in c["b"]["statement"]
            and c["a"]["retrieved"] > c["b"]["retrieved"] for c in group
        )
    assert ids["tune"].isdisjoint(ids["validate"])


def test_dedupe_eval_labels_are_not_sent_to_jev(evaluator, tmp_path, monkeypatch, capsys):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case("tune"), _case("validate")]))
    monkeypatch.setattr(evaluator, "CASES", path)
    calls = []

    def judge(pairs):
        calls.append(pairs)
        assert all(isinstance(e, KnowledgeEntry) for p in pairs for e in p)
        assert all("label" not in e.model_dump() and "keep" not in e.model_dump() for p in pairs for e in p)
        return [_judgment() for _ in pairs]

    monkeypatch.setattr(evaluator, "judge_pairs", judge)
    assert evaluator.main() == 0
    assert len(calls) == 2
    assert capsys.readouterr().out == (
        "overlap_threshold=0.35 threshold=0.5 wrong=0 missed_conflicts=0 proposal_rate=1.00\naccept\n"
    )


def test_dedupe_eval_does_not_judge_pairs_missed_by_candidates(evaluator, tmp_path, monkeypatch, capsys):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([
        _case("tune"), _case("validate", same_source=False),
        _case("validate", label="conflicting", same_source=False),
    ]))
    monkeypatch.setattr(evaluator, "CASES", path)
    calls = []
    monkeypatch.setattr(evaluator, "judge_pairs", lambda pairs: calls.append(pairs) or [
        _judgment() for _ in pairs
    ])
    assert evaluator.main() == 1
    assert len(calls) == 1
    assert "missed_conflicts=1 proposal_rate=0.00" in capsys.readouterr().out


def test_dedupe_eval_threshold_is_chosen_only_from_tune(evaluator, tmp_path, monkeypatch, capsys):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case("tune", "unrelated"), _case("validate")]))
    monkeypatch.setattr(evaluator, "CASES", path)
    monkeypatch.setattr(evaluator, "judge_pairs", lambda pairs: [_judgment(confidence=0.7)])
    assert evaluator.main() == 1
    assert "threshold=0.75 wrong=0" in capsys.readouterr().out


@pytest.mark.parametrize("proposal", [
    Routing(bucket="proposal", old="tech-1", by="tech-2", reason="duplicate"),
    Routing(bucket="proposal", old="tech-2", by="tech-1", reason="updates"),
])
def test_dedupe_eval_wrong_direction_or_reason_counts_as_wrong(evaluator, proposal):
    assert evaluator._wrong(_case("validate"), proposal)


def test_dedupe_eval_jev_failure_is_reported(evaluator, tmp_path, monkeypatch, capsys):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case("tune"), _case("validate")]))
    monkeypatch.setattr(evaluator, "CASES", path)

    def fail(pairs):
        raise RuntimeError("API failed")

    monkeypatch.setattr(evaluator, "judge_pairs", fail)
    assert evaluator.main() == 2
    assert "error: API failed" in capsys.readouterr().err


def test_dedupe_eval_overlap_threshold_comes_from_tune_only(evaluator):
    cases = json.loads((ROOT / "scripts/eval/dedupe_cases.json").read_text())
    tune = [c for c in cases if c["split"] == "tune"]
    assert evaluator._choose_overlap_threshold(tune) == 0.2


def test_dedupe_cli_finds_qualitative_duplicate_from_tune(tmp_path, monkeypatch):
    from medo_cli import main
    from medo_core.knowledge import KnowledgeStore
    from typer.testing import CliRunner

    monkeypatch.setenv("MEDO_HOME", str(tmp_path))
    cases = json.loads((ROOT / "scripts/eval/dedupe_cases.json").read_text())
    case = next(c for c in cases if c["a"]["entry_id"] == "tech-3")
    store = KnowledgeStore(tmp_path / "knowledge")
    for side in ("a", "b"):
        store.save(KnowledgeEntry(**case[side]))
    monkeypatch.setattr(main, "judge_pairs", lambda *_a, **_k: [_judgment()])
    result = CliRunner().invoke(main.app, [
        "knowledge", "dedupe", "--kind", "tech", "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["candidates"] == [["tech-3", "tech-4"]]
