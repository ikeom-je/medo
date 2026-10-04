import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval" / "run_implies_eval.py"


def _eval():
    spec = importlib.util.spec_from_file_location("implies_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_implies_cases_cover_each_split_and_label():
    cases = json.loads(SCRIPT.with_name("implies_cases.json").read_text())
    counts = Counter((c["split"], c["label"]) for c in cases)
    for split in ("tune", "validate"):
        assert sum(n for (s, _), n in counts.items() if s == split) >= 12
        assert all(counts[split, label] >= 4 for label in ("determines", "narrows", "none"))


def test_implies_eval_sends_context_without_labels(monkeypatch):
    module = _eval()
    contexts = []

    def judge(items, pairs, context):
        assert len(items) == 2 and len(pairs) == 1
        assert "label" not in json.dumps([items, pairs, context])
        assert "split" not in json.dumps([items, pairs, context])
        contexts.append(context)
        return {"implies": {pairs[0]: {"choice": "none", "confidence": 0.9}}}

    monkeypatch.setattr(module, "judge_uncertainty", judge)
    cases = [{"a": "A", "b": "B", "context": {"description": "scope"},
              "label": "none", "split": "tune"}]
    assert module._judge(cases) == [{"choice": "none", "confidence": 0.9}]
    assert contexts == [{"description": "scope"}]


def test_implies_threshold_selected_only_from_tune():
    module = _eval()
    cases = [{"label": "none"}, {"label": "determines"}]
    judgments = [{"choice": "narrows", "confidence": 0.7},
                 {"choice": "determines", "confidence": 0.95}]
    assert module._choose_threshold(cases, judgments) == 0.75
    assert module._edge({"choice": "none", "confidence": 1}, 0.5) == "none"
    assert module._edge({"choice": "determines", "confidence": 0.75}, 0.75) == "determines"


def test_implies_threshold_cannot_suppress_false_edges():
    module = _eval()
    assert module._choose_threshold([{"label": "none"}],
                                     [{"choice": "narrows", "confidence": 1}]) is None


@pytest.mark.parametrize("judgment,expected", [
    ({"choice": "determines", "confidence": 0.9}, 0),
    ({"choice": "narrows", "confidence": 0.9}, 1),
])
def test_implies_eval_acceptance_and_recording(monkeypatch, tmp_path, capsys, judgment, expected):
    module = _eval()
    cases = json.loads(module.CASES.read_text())

    def judge(selected):
        return [{"choice": "none", "confidence": 0.9} if c["label"] == "none"
                else judgment if c["label"] == "determines"
                else {"choice": "narrows", "confidence": 0.9} for c in selected]

    monkeypatch.setattr(module, "_judge", judge)
    monkeypatch.setattr(module, "RUNS", tmp_path / "runs.jsonl")
    assert module.main() == expected
    out = capsys.readouterr().out
    assert ("accept" if expected == 0 else "reject") in out
    record = json.loads(module.RUNS.read_text())
    assert record["output"] == out
    assert len(record["tune"]) == len(record["validate"]) == 12
    assert record["cases_sha256"]
    assert record["threshold"] == 0.5
    assert len(cases) == 24


def test_implies_eval_api_failure_is_error(monkeypatch, tmp_path, capsys):
    module = _eval()
    monkeypatch.setattr(module, "_judge", lambda _: (_ for _ in ()).throw(RuntimeError("HTTP 500")))
    monkeypatch.setattr(module, "RUNS", tmp_path / "runs.jsonl")
    assert module.main() == 2
    assert "error: HTTP 500" in capsys.readouterr().err


def test_implies_eval_rejects_missing_label_coverage(monkeypatch, tmp_path, capsys):
    module = _eval()
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([{"split": "tune", "label": "none"}]))
    monkeypatch.setattr(module, "CASES", path)
    monkeypatch.setattr(module, "RUNS", tmp_path / "runs.jsonl")
    monkeypatch.setattr(module, "_judge", lambda _: pytest.fail("invalid cases must not reach Jev"))
    assert module.main() == 2
    assert "error:" in capsys.readouterr().err
