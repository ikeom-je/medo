"""TypeSafe System One の候補分類アダプタ。"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from medo_core.research import Candidate, Verdict

API_URL = "https://api.typesafe.ai/v1/systemone"


def judge_candidates(
    candidates: list[Candidate], aspects: dict[str, str], context: dict | None = None
) -> list[Verdict]:
    """候補群を一度の System One リクエストで判定する。

    context には案件の業界・goal・課題を渡す。これが無いと「この案件の現状把握に
    効くか」を問うても、モデルは案件を知らないまま答えることになる。
    """
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY が設定されていません")

    aspect_criteria = {**aspects, "none": "上記のどれにも当たらない"}
    questions = {}
    for index, candidate in enumerate(candidates):
        prefix = f"c{index}"
        candidate_path = f"candidates[{index}]"
        questions[f"{prefix}_relevance"] = {
            "type": "score",
            "instructions": (
                f"`{candidate_path}` が案件の現状把握にどれだけ効くかを"
                "判定する。"
            ),
            "criteria": [
                "案件の現状把握に効かない",
                "背景として有用",
                "核心的な実態が分かる",
            ],
        }
        questions[f"{prefix}_aspect"] = {
            "type": "choice",
            "instructions": f"`{candidate_path}` が最も寄与する調査観点を選ぶ。",
            "criteria": aspect_criteria,
        }
        questions[f"{prefix}_is_primary"] = {
            "type": "noul",
            "instructions": f"`{candidate_path}` は一次資料かを判定する。",
        }
        questions[f"{prefix}_worth_descending"] = {
            "type": "noul",
            "instructions": (
                f"`{candidate_path}` から、さらにリンクを辿って下の階層へ"
                "降りる価値があるか。"
            ),
            "criteria": {
                "true": "一覧・目次・リンク集・関連資料への導線があり、未取得の"
                        "詳細へ辿り着ける見込みがある",
                "false": "内容が完結しており、辿れる先が既出情報か無関係",
            },
        }

    payload = json.dumps(
        {
            "state": {
                "project": context or {},
                "candidates": [candidate.model_dump() for candidate in candidates],
                "aspects": aspects,
            },
            "model": "jev-latest",
            "questions": questions,
        }
    ).encode()
    request = Request(
        API_URL,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request) as response:
            body = json.load(response)
        answers = body["answers"]
    except HTTPError as e:
        # 本文を読まないと、API仕様違反の原因がステータスコードだけになる。
        raise RuntimeError(f"Jevの判定に失敗しました: {e} {e.read().decode(errors='replace')}") from e
    except (KeyError, OSError, URLError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Jevの判定に失敗しました: {e}") from e

    try:
        return [
            Verdict(
                url=candidate.url,
                relevance=_normalized_score(answers[f"c{index}_relevance"]),
                aspect=answers[f"c{index}_aspect"]["choice"],
                is_primary=answers[f"c{index}_is_primary"]["noul"],
                worth_descending=answers[f"c{index}_worth_descending"]["noul"],
            )
            for index, candidate in enumerate(candidates)
        ]
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError(f"Jevの応答が不正です: {e}") from e


def _normalized_score(answer: dict) -> float:
    """score はレベル番号の範囲で返る(3段なら0〜2)。Verdictの0〜1契約へ写す。"""
    levels = len(answer.get("legend") or {}) or len(answer.get("probabilities") or {})
    if levels < 2:
        raise ValueError(f"score の水準数が不正です: {levels}")
    return min(1.0, max(0.0, answer["score"] / (levels - 1)))
