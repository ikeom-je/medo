"""PRが人間レビューを要するか(git.md Section 1 step 7)をJevに判定させる。

Claudeの判定の第二意見として使う。Claudeと食い違ったら人間レビュー側に倒す。

    python scripts/jev_merge_judge.py <PR番号> [--repo owner/name]
"""

import argparse
import json
import os
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.typesafe.ai/v1/systemone"
# 大きなdiffを丸ごと送らない。判定に要るのは変更の性質で、全行ではない。
DIFF_BUDGET = 40_000

QUESTIONS = {
    "contract_change": {
        "type": "noul",
        "instructions": (
            "`pr` の変更が、CLIのコマンド体系・オプション・出力形式、保存データのスキーマ、"
            "Storageパス、またはSkill本文がCLIに求める呼び出し方(Skill契約)を変えるか。"
        ),
        "criteria": {
            "true": "既存の呼び出し側(Skill・保存済みデータ・CLI利用者)が影響を受ける変更を含む",
            "false": (
                "内部実装・テスト・ドキュメントのみで、外から見える契約は変わらない。"
                "`pr.files` が設計文書・計画だけで、将来の契約変更を記述しているにすぎない場合もこちら"
            ),
        },
    },
    "cloud_billing": {
        "type": "noul",
        "instructions": (
            "`pr` が、クラウドの認証・課金が絡む変更、または外部の有料APIへの実クライアント"
            "呼び出しを初めて追加するか。"
        ),
        "criteria": {
            "true": "新たにクラウド認証・課金・外部有料APIの実呼び出しが入る",
            "false": (
                "そうした呼び出しは追加されない(既存の呼び出しの流用、テスト用の偽物のみ、"
                "または設計文書が将来の呼び出しを記述しているだけ)"
            ),
        },
    },
    "unresolved_severe": {
        "type": "noul",
        "instructions": (
            "`pr.body` の相互レビュー記録に、解消されていない重大指摘が残っているか。"
        ),
        "criteria": {
            "true": "未解決の重大指摘がある、またはレビュー記録そのものが無い",
            "false": "重大指摘はすべて解消済みと記録されている",
        },
    },
}


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def collect(pr: str, repo: str) -> dict:
    meta = json.loads(_gh("pr", "view", pr, "-R", repo, "--json", "title,body,files,baseRefName"))
    diff = _gh("pr", "diff", pr, "-R", repo)
    return {
        "title": meta["title"],
        "base": meta["baseRefName"],
        "body": meta["body"],
        "files": [f["path"] for f in meta["files"]],
        "diff": diff[:DIFF_BUDGET],
        "diff_truncated": len(diff) > DIFF_BUDGET,
    }


def judge(pr_state: dict) -> dict[str, float]:
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY が設定されていません")
    payload = json.dumps(
        {"state": {"pr": pr_state}, "model": "jev-latest", "questions": QUESTIONS}
    ).encode()
    request = Request(
        API_URL,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            answers = json.load(response)["answers"]
        return {qid: float(answers[qid]["noul"]) for qid in QUESTIONS}
    except HTTPError as e:
        raise RuntimeError(f"Jevの判定に失敗しました: {e} {e.read().decode(errors='replace')}") from e
    except (KeyError, TypeError, ValueError, OSError, URLError) as e:
        raise RuntimeError(f"Jevの判定に失敗しました: {e}") from e


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pr")
    parser.add_argument("--repo", default="ikeom-je/medo")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    try:
        probabilities = judge(collect(args.pr, args.repo))
    except (RuntimeError, subprocess.CalledProcessError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    flagged = [qid for qid, p in probabilities.items() if p >= args.threshold]
    print(
        json.dumps(
            {"pr": args.pr, "probabilities": probabilities, "needs_human_review": bool(flagged),
             "flagged": flagged},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
