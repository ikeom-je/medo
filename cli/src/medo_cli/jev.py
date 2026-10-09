"""TypeSafe System One の候補分類アダプタ。"""

import json
import os
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from medo_core.knowledge import KnowledgeEntry
from medo_core.knowledge_dedupe import PairJudgment
from medo_core.research import Candidate, Verdict

API_URL = "https://api.typesafe.ai/v1/systemone"


class JevUnavailable(RuntimeError):
    """API鍵が未設定で、Jevの判定を利用できない。"""


def _post(payload: dict, api_key: str, timeout: int | None = None) -> dict:
    request = Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        options = {} if timeout is None else {"timeout": timeout}
        with urlopen(request, **options) as response:
            answers = json.load(response)["answers"]
        if not isinstance(answers, dict):
            raise ValueError("answers がオブジェクトではありません")
        return answers
    except HTTPError as exc:
        raise RuntimeError(
            f"Jevの判定に失敗しました: {exc} {exc.read().decode(errors='replace')}"
        ) from exc
    except (KeyError, TypeError, ValueError, OSError, URLError) as exc:
        raise RuntimeError(f"Jevの判定に失敗しました: {exc}") from exc


def judge_pairs(
    pairs: list[tuple[KnowledgeEntry, KnowledgeEntry]],
    evidence: dict[str, str] | None = None,
    timeout: int = 60,
) -> list[PairJudgment]:
    """各組の関係・範囲・記述時点・残す側を、一度のリクエストで判定する。"""
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise JevUnavailable("TYPESAFE_API_KEY が設定されていません")
    if not pairs:
        return []
    questions = {}
    for n, _ in enumerate(pairs):
        a, b = f"`pairs[{n}].a`", f"`pairs[{n}].b`"
        questions[f"p{n}_relation"] = {
            "type": "choice",
            "instructions": f"{a} と {b} の関係を分類する。数値が同じかどうかは判断しない。",
            "criteria": {
                "duplicate": "同じ範囲・同じ時点の同じ事実を述べている",
                "updates": "同じ範囲・同じ指標について、異なる時点の値を述べている",
                "complementary": "同じ対象の別の側面を述べている",
                "conflicting": "同じ範囲・同じ時点・同じ指標なのに述べている値や結論が食い違う",
                "unrelated": "関係が無い",
            },
        }
        questions[f"p{n}_same_scope"] = {
            "type": "noul",
            "instructions": f"{a} と {b} の地域・対象・指標が一致しているか。時点は問わない。",
        }
        questions[f"p{n}_newer"] = {
            "type": "choice",
            "instructions": (
                f"{a} と {b} が述べている時点(調査年・発表年・版)の関係。"
                "取得日(retrieved)では判断しない。"
            ),
            "criteria": {
                "a": "a のほうが後の時点", "b": "b のほうが後の時点",
                "same": "同じ時点", "unknown": "時点が読み取れない",
            },
        }
        questions[f"p{n}_keep"] = {
            "type": "choice",
            "instructions": (
                f"{a} と {b} が同じ事実を述べているとき、残すべきほうを選ぶ。"
                "基準は出典が一次資料か、記述が具体的か。新しさは基準にしない。"
            ),
            "criteria": {"a": "a を残す", "b": "b を残す"},
        }
    answers = _post({
        "state": {"pairs": [
            {"a": _entry_state(a, evidence), "b": _entry_state(b, evidence)} for a, b in pairs
        ]},
        "model": "jev-latest",
        "questions": questions,
    }, api_key, timeout)
    try:
        judgments = []
        for n, _ in enumerate(pairs):
            relation, rc = _choice(answers[f"p{n}_relation"], questions[f"p{n}_relation"])
            newer, nc = _choice(answers[f"p{n}_newer"], questions[f"p{n}_newer"])
            keep, kc = _choice(answers[f"p{n}_keep"], questions[f"p{n}_keep"])
            judgments.append(PairJudgment(
                relation=relation, relation_confidence=rc,
                same_scope=_probability(answers[f"p{n}_same_scope"]["noul"]),
                newer=newer, newer_confidence=nc, keep=keep, keep_confidence=kc,
            ))
        return judgments
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Jevの応答が不正です: {exc}") from exc


def _entry_state(entry: KnowledgeEntry, evidence: dict[str, str] | None) -> dict:
    state = entry.model_dump(mode="json", include={
        "entry_id", "statement", "value", "unit", "source", "retrieved", "note",
    })
    if evidence and entry.entry_id in evidence:
        state["evidence"] = evidence[entry.entry_id]
    return state


def _probability(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"確率の範囲外です: {value}")
    return value


def _choice(answer: dict, question: dict) -> tuple[str, float]:
    choice = answer["choice"]
    if choice not in question["criteria"]:
        raise ValueError(f"選択肢が不正です: {choice}")
    return choice, _probability(answer["confidence"])


def judge_support(
    statement: str, quote: str, context: dict
) -> Literal["supported", "doubtful", "unjudged"]:
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY が設定されていません")

    payload = {
        "state": {"statement": statement, "quote": quote, "context": context},
        "model": "jev-latest",
        "questions": {
            "support": {
                "type": "noul",
                "instructions": (
                    "`quote` の年・地域・指標が `statement` の主張と対応しているか判定する。"
                    "数値そのものの一致は判定しない。"
                ),
                "criteria": {
                    "true": "抜粋の年・地域・指標が主張と対応している",
                    "false": "年・地域・指標のいずれかが異なる、または対応を確認できない",
                },
            }
        },
    }
    try:
        probability = _post(payload, api_key, timeout=10)["support"]["noul"]
        if isinstance(probability, bool) or not isinstance(probability, (int, float)):
            raise ValueError("noul が数値ではありません")
        if not 0 <= probability <= 1:
            raise ValueError(f"noul が確率の範囲外です: {probability}")
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Jevの判定に失敗しました: {exc}") from exc
    return "supported" if probability >= 0.5 else "doubtful"


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

    answers = _post(
        {
            "state": {
                "project": context or {},
                "candidates": [candidate.model_dump() for candidate in candidates],
                "aspects": aspects,
            },
            "model": "jev-latest",
            "questions": questions,
        },
        api_key,
    )

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


def judge_uncertainty(items: list[dict], pairs: list[tuple[str, str]], context: dict) -> dict:
    """仮説の含意、策の選択への影響、検証の手間を分類する。"""
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise JevUnavailable("TYPESAFE_API_KEY が設定されていません")
    texts = {item["id"]: item["text"] for item in items}
    questions = {}
    for n, _ in enumerate(pairs):
        questions[f"i{n}_implies"] = {
            "type": "choice",
            "instructions": (
                f"`pairs[{n}].a` の仮説が確定すると、`pairs[{n}].b` の仮説も決まるか。"
                "`context` の明示された前提と確認済みの条件を使い、AからBへの向きを判定する。"
                "他の条件が確認済みで残る条件がAだけなら、Aの確定でBも決まる。"
                "未確認の条件が別に残る必要条件だけなら、Bは絞られるだけ。"
                "同じ課題に属するだけでは依存関係とはしない。数値の計算や一致は判定しない。"
            ),
            "criteria": {
                "determines": "Aが確定するとBの成立・不成立も決まる。直接の含意、または"
                              "contextで他の条件が確認済みでAが唯一残る条件となる依存関係",
                "narrows": "Aが確定するとBの可能性が大きく絞られるが、未確認の条件が別に"
                           "残るためBの成立・不成立はまだ決まらない",
                "none": "Aが確定してもBは決まらず、可能性も大きく絞られない。共通の課題・"
                        "目的があるだけの独立した仮説を含む",
            },
        }
    for n, item in enumerate(items):
        if item["needs_relevance"]:
            questions[f"r{n}_relevant"] = {
                "type": "noul",
                "instructions": (
                    f"`items[{n}].text` が解消したら、`context.options` のどの策を取るかが"
                    "変わり得るか。結びつく課題も踏まえて判定する。"
                ),
                "criteria": {
                    "true": "解消した結果によって策の選択が変わり得る",
                    "false": "解消しても策の選択は変わらない",
                },
            }
        questions[f"e{n}_effort"] = {
            "type": "choice",
            "instructions": f"`items[{n}].text` を確かめるのに必要な手間を選ぶ。",
            "criteria": {
                "ask": "関係者にすぐ聞けば確かめられる",
                "research": "資料や現状の調査が要る",
                "experiment": "実証実験が要る",
            },
        }
    out = {"implies": {}, "decision_relevant": {}, "effort": {}}
    if not questions:
        return out
    answers = _post({
        "model": "jev-latest",
        "state": {"items": items, "pairs": [{"a": texts[a], "b": texts[b]} for a, b in pairs],
                  "context": context},
        "questions": questions,
    }, api_key, timeout=60)
    try:
        for n, pair in enumerate(pairs):
            choice, confidence = _choice(answers[f"i{n}_implies"], questions[f"i{n}_implies"])
            out["implies"][pair] = {"choice": choice, "confidence": confidence}
        for n, item in enumerate(items):
            if item["needs_relevance"]:
                out["decision_relevant"][item["id"]] = _probability(
                    answers[f"r{n}_relevant"]["noul"]
                )
            effort, _ = _choice(answers[f"e{n}_effort"], questions[f"e{n}_effort"])
            out["effort"][item["id"]] = effort
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Jevの応答が不正です: {exc}") from exc
    return out
