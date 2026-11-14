"""正解付きの組で候補生成から振り分けまでを評価し、閾値を決める。"""

import json
import sys
from pathlib import Path

from medo_cli.jev import judge_pairs
from medo_core.knowledge import KnowledgeEntry
from medo_core.knowledge_dedupe import Routing, candidate_pairs, check_components, route

CASES = Path(__file__).with_name("dedupe_cases.json")
MERGE = {"duplicate", "updates"}
MIN_PROPOSAL_RATE = 0.8
THRESHOLDS = [x / 100 for x in range(50, 100, 5)]
OVERLAP_THRESHOLDS = [x / 100 for x in range(35, -1, -5)]


def _wrong(case: dict, routing: Routing) -> bool:
    if routing.bucket != "proposal":
        return False
    if case["label"] not in MERGE or routing.reason != case["label"]:
        return True
    kept = case[case["keep"]]["entry_id"]
    return routing.by != kept


def _choose_overlap_threshold(tune):
    required = [
        (KnowledgeEntry(**c["a"]), KnowledgeEntry(**c["b"])) for c in tune
        if c["label"] in MERGE | {"conflicting"}
    ]
    return next(
        t for t in OVERLAP_THRESHOLDS
        if all(candidate_pairs([a, b], overlap_threshold=t) for a, b in required)
    )


def _judge_cases(cases, overlap_threshold):
    pairs = [(KnowledgeEntry(**c["a"]), KnowledgeEntry(**c["b"])) for c in cases]
    candidates = [bool(candidate_pairs([a, b], overlap_threshold=overlap_threshold)) for a, b in pairs]
    selected = [p for p, candidate in zip(pairs, candidates, strict=True) if candidate]
    judged = judge_pairs(selected) if selected else []
    if len(judged) != len(selected):
        raise RuntimeError("Jevの応答の組数が一致しません")
    answers = iter(judged)
    return pairs, [next(answers) if candidate else None for candidate in candidates]


def _final_routes(pairs, judgments, threshold):
    routed = [
        route(a, b, j, threshold) if j is not None else Routing(bucket="held")
        for (a, b), j in zip(pairs, judgments, strict=True)
    ]
    conflicts = [
        (a.entry_id, b.entry_id) for (a, b), r in zip(pairs, routed, strict=True)
        if r.bucket == "conflict"
    ]
    keep, _ = check_components([r for r in routed if r.bucket == "proposal"], conflicts)
    return [
        Routing(bucket="held") if r.bucket == "requery" or (r.bucket == "proposal" and r not in keep)
        else r for r in routed
    ]


def main() -> int:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    tune = [c for c in cases if c["split"] == "tune"]
    val = [c for c in cases if c["split"] == "validate"]
    overlap = _choose_overlap_threshold(tune)
    try:
        pairs, judged = _judge_cases(tune, overlap)
        chosen = next((
            t for t in THRESHOLDS
            if not any(_wrong(c, r) for c, r in zip(tune, _final_routes(pairs, judged, t), strict=True))
        ), None)
        if chosen is None:
            print("error: 調整用の組で誤統合0件になる閾値がありません", file=sys.stderr)
            return 1
        vp, vj = _judge_cases(val, overlap)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    routed = _final_routes(vp, vj, chosen)
    wrong = sum(_wrong(c, r) for c, r in zip(val, routed, strict=True))
    missed_conflicts = sum(
        c["label"] == "conflicting" and r.bucket != "conflict"
        for c, r in zip(val, routed, strict=True)
    )
    merge_cases = [r for c, r in zip(val, routed, strict=True) if c["label"] in MERGE]
    rate = sum(r.bucket == "proposal" for r in merge_cases) / len(merge_cases) if merge_cases else 0.0
    print(f"overlap_threshold={overlap} threshold={chosen} wrong={wrong} "
          f"missed_conflicts={missed_conflicts} proposal_rate={rate:.2f}")
    ok = wrong == 0 and missed_conflicts == 0 and rate >= MIN_PROPOSAL_RATE
    print("accept" if ok else "reject")
    if not ok:
        for c, j, r in zip(val, vj, routed, strict=True):
            print(f"{c['a']['entry_id']}/{c['b']['entry_id']} label={c['label']} "
                  f"judgment={j.model_dump() if j else None} routing={r.model_dump()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
