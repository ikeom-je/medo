"""正解付きの組で implies の判定を評価し、閾値を決める。"""

import hashlib
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import medo_cli.jev as jev
from medo_cli.jev import judge_uncertainty

CASES = Path(__file__).with_name("implies_cases.json")
RUNS = Path(__file__).with_name("implies_runs.jsonl")
THRESHOLDS = [x / 100 for x in range(50, 100, 5)]
MAX_FALSE_EDGE_RATE = 0.1
MIN_DETERMINES_RECALL = 0.8


def _judge_case(case):
    items = [{"id": "hyp-1", "text": case["a"], "kind": "hyp", "needs_relevance": False},
             {"id": "hyp-2", "text": case["b"], "kind": "hyp", "needs_relevance": False}]
    pair = ("hyp-1", "hyp-2")
    out = judge_uncertainty(items, [pair], case["context"])
    return out["implies"][pair]


def _judge(cases):
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(_judge_case, cases))


def _edge(judgment, threshold):
    return (judgment["choice"] if judgment["choice"] in ("determines", "narrows")
            and judgment["confidence"] >= threshold else "none")


def _false_rate(cases, judgments, threshold):
    nones = [j for c, j in zip(cases, judgments, strict=True) if c["label"] == "none"]
    return sum(_edge(j, threshold) != "none" for j in nones) / len(nones)


def _choose_threshold(cases, judgments):
    return next((t for t in THRESHOLDS
                 if _false_rate(cases, judgments, t) <= MAX_FALSE_EDGE_RATE), None)


def _validate_cases(cases):
    counts = Counter((c["split"], c["label"]) for c in cases)
    valid_keys = {(s, label) for s in ("tune", "validate")
                  for label in ("determines", "narrows", "none")}
    if set(counts) - valid_keys or any(counts[key] < 4 for key in valid_keys):
        raise ValueError("各 split に determines / narrows / none が各4組以上必要です")
    if not all(isinstance(c["a"], str) and isinstance(c["b"], str)
               and isinstance(c["context"], dict) for c in cases):
        raise ValueError("評価の組には本文と context が必要です")


def _record(record, output):
    record["output"] = "\n".join(output) + "\n"
    with RUNS.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    output = []
    record = {"cases_sha256": hashlib.sha256(CASES.read_bytes()).hexdigest(),
              "jev_sha256": hashlib.sha256(Path(jev.__file__).read_bytes()).hexdigest(),
              "tune": [], "validate": [], "threshold": None}

    def emit(line, *, error=False):
        output.append(line)
        print(line, file=sys.stderr if error else sys.stdout)

    try:
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        _validate_cases(cases)
        tune = [c for c in cases if c["split"] == "tune"]
        validate = [c for c in cases if c["split"] == "validate"]
        tj = _judge(tune)
        record["tune"] = [{"case": c, "judgment": j} for c, j in zip(tune, tj, strict=True)]
        chosen = _choose_threshold(tune, tj)
        record["threshold"] = chosen
        if chosen is None:
            emit("error: 調整用の組で誤って辺を張る率を1割以下にできる閾値がありません", error=True)
            _record(record, output)
            return 1
        equivalent = [t for t in THRESHOLDS
                      if [_edge(j, t) for j in tj] == [_edge(j, chosen) for j in tj]]
        record["equivalent_thresholds"] = equivalent
        if len(equivalent) > 1:
            emit("tune_thresholds_equivalent=" + ",".join(f"{t:.2f}" for t in equivalent)
                 + " (この範囲では閾値を識別できない)")
        vj = _judge(validate)
        record["validate"] = [{"case": c, "judgment": j} for c, j in zip(validate, vj, strict=True)]
        false_rate = _false_rate(validate, vj, chosen)
        dets = [j for c, j in zip(validate, vj, strict=True) if c["label"] == "determines"]
        det_rate = sum(_edge(j, chosen) == "determines" for j in dets) / len(dets)
        emit(f"threshold={chosen} false_edge_rate={false_rate:.2f} determines_recall={det_rate:.2f}")
        ok = false_rate <= MAX_FALSE_EDGE_RATE and det_rate >= MIN_DETERMINES_RECALL
        emit("accept" if ok else "reject")
        record.update(false_edge_rate=false_rate, determines_recall=det_rate, accepted=ok)
        if not ok:
            for n, (case, judgment) in enumerate(zip(validate, vj, strict=True)):
                if ((case["label"] == "none" and _edge(judgment, chosen) != "none")
                    or (case["label"] == "determines" and _edge(judgment, chosen) != "determines")):
                    emit(f"validate[{n}] label={case['label']} judgment={json.dumps(judgment)}")
        _record(record, output)
        return 0 if ok else 1
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        emit(f"error: {exc}", error=True)
        _record(record, output)
        return 2


if __name__ == "__main__":
    sys.exit(main())
