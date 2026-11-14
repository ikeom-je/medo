"""正解付きレビュー指摘で triage の premise と severity を評価する。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jev_judge import JudgeError, triage  # noqa: E402

CASES_PATH = Path(__file__).with_name("triage_cases.json")
PREMISE_THRESHOLD = 0.5


def main() -> int:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    items = [{key: case[key] for key in ("id", "text", "evidence")} for case in cases]
    try:
        results = triage(items, context="")
    except JudgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print("id          valid  premise  severity (expected -> actual)")
    for case in cases:
        result = results[case["id"]]
        print(
            f"{case['id']:<11} {str(case['label_valid']):<6} "
            f"{result['premise']:.4f}   {case['label_severity']} -> {result['severity']}"
        )

    valid = [results[case["id"]]["premise"] for case in cases if case["label_valid"]]
    invalid = [results[case["id"]]["premise"] for case in cases if not case["label_valid"]]
    correct = sum(
        (results[case["id"]]["premise"] >= PREMISE_THRESHOLD) == case["label_valid"]
        for case in cases
    )
    severity_matches = sum(
        results[case["id"]]["severity"] == case["label_severity"] for case in cases
    )
    print(f"premise_separation: {min(valid):.4f} > {max(invalid):.4f} = {min(valid) > max(invalid)}")
    print(f"premise_accuracy@0.5: {correct}/{len(cases)}")
    print(f"severity_matches: {severity_matches}/{len(cases)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
