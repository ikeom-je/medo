"""開発運用の細かい判断をJevに並列で判定させる(オーケストレータの第二意見)。

    python scripts/jev_judge.py route  <items.json>   # サブタスクの振り先
    python scripts/jev_judge.py triage <items.json>   # レビュー指摘の重大度・妥当性
    python scripts/jev_judge.py merge  <PR番号>        # 人間レビューを要するか(git.md step 7)

items.json は [{"id": "...", "text": "..."}] 。triage は任意で "reviewer" を持てる。
各項目の質問は1リクエストに並べ、Jevが並列に答える。最終判断はオーケストレータが行う。
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.typesafe.ai/v1/systemone"
FILE_DIFF_BUDGET = 20_000
THRESHOLD = 0.5

ROUTES = {
    "claude": (
        "計画・設計・判断、要件との整合性判断、Skill/CLIの契約変更判断、レビュー裁定、"
        "設計正本・steeringの執筆、最終検証、コミット・マージ"
    ),
    "codex": (
        "手順が決まっているコードの実装、テストコードの作成、スキャフォールド・網羅的テスト生成・"
        "マイグレーション、コード・テスト失敗起因のデバッグ、README・CLI使用例のドラフト"
    ),
    "agy": (
        "Web検索(市場・国策・業界動向・技術情報)、依存ライブラリ・CVE調査、エラーログの一次トリアージ、"
        "PDF・スライド・画像からの情報抽出、長いドキュメント/コード全体を読むダイジェスト、"
        "調査レポート・資料のドラフト、スライド・図表の生成"
    ),
}


class JudgeError(RuntimeError):
    pass


def ask(state: dict, questions: dict) -> dict:
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise JudgeError("TYPESAFE_API_KEY が設定されていません")
    payload = json.dumps({"state": state, "model": "jev-latest", "questions": questions}).encode()
    request = Request(
        API_URL,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            answers = json.load(response)["answers"]
    except HTTPError as e:
        raise JudgeError(f"Jevの判定に失敗: {e} {e.read().decode(errors='replace')}") from e
    except (KeyError, OSError, URLError, json.JSONDecodeError) as e:
        raise JudgeError(f"Jevの判定に失敗: {e}") from e
    missing = set(questions) - set(answers)
    if missing:
        raise JudgeError(f"Jevの応答に欠けた質問があります: {sorted(missing)}")
    return answers


def _load_items(path: str) -> list[dict]:
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    if not items or not all("id" in i and "text" in i for i in items):
        raise JudgeError("items は [{\"id\", \"text\"}] の空でない配列である必要があります")
    return items


def route(items: list[dict]) -> dict:
    questions = {}
    for n, _ in enumerate(items):
        questions[f"i{n}_route"] = {
            "type": "choice",
            "instructions": f"`items[{n}].text` の作業を、担当表 `routes` のどの実行主体に振るべきか選ぶ。",
            "criteria": ROUTES,
        }
        questions[f"i{n}_needs_user"] = {
            "type": "noul",
            "instructions": (
                f"`items[{n}].text` は、進める前にユーザーの判断・承認が要るか"
                "(設計の選択、契約・課金の変更、破壊的な操作、方針が決まっていない事項)。"
            ),
        }
    answers = ask({"items": items, "routes": ROUTES}, questions)
    return {
        item["id"]: {
            "route": answers[f"i{n}_route"]["choice"],
            "confidence": answers[f"i{n}_route"].get("confidence"),
            "needs_user": answers[f"i{n}_needs_user"]["noul"],
        }
        for n, item in enumerate(items)
    }


def triage(items: list[dict], context: str) -> dict:
    questions = {}
    for n, _ in enumerate(items):
        questions[f"i{n}_severity"] = {
            "type": "score",
            "instructions": f"`items[{n}].text` のレビュー指摘が、放置した場合にどれだけ害があるか。",
            "criteria": [
                "文言・体裁の問題で、挙動や判断に影響しない",
                "理解や保守を妨げるが、誤った結果は生まない",
                "特定の条件で誤った結果・契約違反・データ不整合を生む",
            ],
        }
        questions[f"i{n}_valid"] = {
            "type": "noul",
            "instructions": (
                f"`items[{n}].text` の指摘は、`context` に照らして事実として正しく、"
                "かつこの変更の範囲で対処すべきものか。"
            ),
            "criteria": {
                "true": "指摘の前提が正しく、今回の変更が招いた・今回直すべき問題である",
                "false": "前提の誤読、既に対処済み、範囲外の要望、または好みの問題",
            },
        }
    answers = ask({"items": items, "context": context}, questions)
    result = {}
    for n, item in enumerate(items):
        severity = answers[f"i{n}_severity"]
        levels = len(severity.get("legend") or {}) or len(severity.get("probabilities") or {})
        if levels < 2:
            raise JudgeError(f"score の水準数が不正です: {levels}")
        result[item["id"]] = {
            "severity": min(1.0, max(0.0, severity["score"] / (levels - 1))),
            "valid": answers[f"i{n}_valid"]["noul"],
        }
    return result


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def _split_diff(diff: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for chunk in re.split(r"(?m)^(?=diff --git )", diff):
        m = re.match(r"diff --git a/(\S+) b/", chunk)
        if m:
            files[m.group(1)] = chunk
    return files


def merge(pr: str, repo: str) -> dict:
    meta = json.loads(_gh("pr", "view", pr, "-R", repo, "--json", "title,body,baseRefName"))
    if not re.search(r"(?m)^review: ", meta["body"]):
        raise JudgeError("PR本文に `review:` 記録がありません(git.md step 6 の記録漏れ)")
    files = _split_diff(_gh("pr", "diff", pr, "-R", repo))
    judged = {p: d for p, d in files.items() if len(d) <= FILE_DIFF_BUDGET}
    unjudged = sorted(set(files) - set(judged))
    questions = {}
    paths = sorted(judged)
    for n, _ in enumerate(paths):
        questions[f"f{n}_contract"] = {
            "type": "noul",
            "instructions": (
                f"`files[{n}].diff` の変更が、CLIのコマンド体系・オプション・出力形式、保存データの"
                "スキーマ、Storageパス、またはSkill本文がCLIに求める呼び出し方(Skill契約)を変えるか。"
            ),
            "criteria": {
                "true": (
                    "既存の呼び出し側(Skill・保存済みデータ・CLI利用者)が影響を受ける変更。"
                    "後方互換でも、CLIのコマンド・オプション・スキーマ・Storageパスの新規追加を含む"
                ),
                "false": (
                    "内部実装・テスト・ドキュメントのみ。設計文書・計画が将来の変更を"
                    "記述しているだけの場合もこちら"
                ),
            },
        }
        questions[f"f{n}_billing"] = {
            "type": "noul",
            "instructions": (
                f"`files[{n}].diff` が、クラウドの認証・課金が絡む変更、または外部の有料APIへの"
                "実クライアント呼び出しを初めて追加するか。"
            ),
            "criteria": {
                "true": "新たにクラウド認証・課金・外部有料APIの実呼び出しが入る",
                "false": "追加されない(既存呼び出しの流用・テスト用の偽物・将来の記述のみ)",
            },
        }
    state = {
        "pr": {"title": meta["title"], "base": meta["baseRefName"], "body": meta["body"]},
        "files": [{"path": p, "diff": judged[p]} for p in paths],
    }
    answers = ask(state, questions) if questions else {}
    per_file = {
        p: {
            "contract_change": answers[f"f{n}_contract"]["noul"],
            "cloud_billing": answers[f"f{n}_billing"]["noul"],
        }
        for n, p in enumerate(paths)
    }
    flagged = sorted(
        f"{p}:{k}" for p, r in per_file.items() for k, v in r.items() if v >= THRESHOLD
    )
    return {
        "per_file": per_file,
        "flagged": flagged,
        "unjudged_files": unjudged,
        "needs_human_review": bool(flagged),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("route").add_argument("items")
    p_triage = sub.add_parser("triage")
    p_triage.add_argument("items")
    p_triage.add_argument("--context", default="", help="判定の前提(設計の要点・diffの要約)")
    p_merge = sub.add_parser("merge")
    p_merge.add_argument("pr")
    p_merge.add_argument("--repo", default="ikeom-je/medo")
    args = parser.parse_args()
    try:
        if args.mode == "route":
            result = route(_load_items(args.items))
        elif args.mode == "triage":
            result = triage(_load_items(args.items), args.context)
        else:
            result = merge(args.pr, args.repo)
    except (JudgeError, subprocess.CalledProcessError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
