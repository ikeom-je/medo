"""深掘り調査の計画を決定論的に組み立てる。"""

from pydantic import BaseModel, Field, field_validator

ASPECTS = {
    "actor_org": "登場人物・組織(誰が関与しているか)",
    "relations": "関係各所(取引・委託・規制・業界団体)",
    "policy": "国・自治体の施策状況(制度・補助・規制の動向)",
    "supply_chain": "サプライチェーンとデータ/情報/物のフロー",
    "workflow": "関係者の作業とワークフロー",
    "market": "市場規模・競合・トレンド",
}


class DepthProfile(BaseModel):
    """調査の探索範囲。"""

    name: str
    max_hops: int
    max_pages: int
    primary_weight: float = Field(ge=0, le=1)
    aspects: tuple[str, ...]


class Candidate(BaseModel):
    """検索で得た、まだ開いていないページ候補。"""

    url: str
    title: str = ""
    snippet: str = ""
    hop: int = 1
    parent_url: str = ""


class Verdict(BaseModel):
    """候補に対する分類器の判定値。"""

    url: str
    relevance: float = Field(ge=0, le=1)
    aspect: str
    is_primary: float = Field(ge=0, le=1)
    worth_descending: float = Field(ge=0, le=1)

    @field_validator("aspect")
    @classmethod
    def aspect_must_be_known(cls, value: str) -> str:
        if value not in (*ASPECTS, "none"):
            raise ValueError("aspect は ASPECTS のキーまたは none である必要があります")
        return value


_ALL_ASPECTS = tuple(ASPECTS)

PROFILES = {
    "scan": DepthProfile(
        name="scan",
        max_hops=1,
        max_pages=5,
        primary_weight=0.0,
        aspects=("actor_org", "market"),
    ),
    "structural": DepthProfile(
        name="structural",
        max_hops=3,
        max_pages=20,
        primary_weight=0.5,
        aspects=_ALL_ASPECTS,
    ),
    "deep": DepthProfile(
        # 一次資料はポータル→検索→一覧→詳細→PDFと辿るため、3階層では届かない。
        name="deep",
        max_hops=6,
        max_pages=60,
        primary_weight=1.0,
        aspects=_ALL_ASPECTS,
    ),
}

FETCH_POLICY = (
    "robots.txt とサイト利用規約に従う",
    "認証・有料壁を回避しない",
    "同一サイトへの連続取得は間隔を空ける",
    "本文の保存は引用の範囲に留め、出典URLと資料名を必ず併記する",
    "個人情報を含むページは保存せず、必要なら出典URLのみ残す",
    "資料の発行日と retrieved(取得日)を混同しない。古い一次資料を最新と誤認しない",
)

STOP_CONDITIONS = (
    "上限ページ数に到達",
    "ユーザーが止めた",
    "model.coverage / model.links の該当項目が解消した",
)


def research_plan(
    profile_name: str, open_findings: dict, node_texts: dict[str, str] | None = None
) -> dict:
    """深度、調査観点、停止条件、解消対象の診断項目を返す。

    node_texts はノードIDから本文への対応。IDだけでは何を調べるか決められない。
    """
    try:
        profile = PROFILES[profile_name]
    except KeyError as e:
        raise ValueError(f"未知の深度プロファイルです: {profile_name}") from e

    texts = node_texts or {}
    findings_to_resolve = {
        section: {
            name: [{"id": node_id, "text": texts.get(node_id, "")} for node_id in values]
            for name, values in open_findings.get(section, {}).items()
            if values
        }
        for section in ("links", "coverage")
    }
    return {
        "profile": profile.model_dump(mode="json"),
        "aspects": [
            {"name": aspect, "description": ASPECTS[aspect]}
            for aspect in profile.aspects
        ],
        "stop_conditions": STOP_CONDITIONS,
        "fetch_policy": FETCH_POLICY,
        "findings_to_resolve": findings_to_resolve,
    }


def triage(
    candidates: list[Candidate],
    verdicts: list[Verdict],
    profile_name: str,
    opened_count: int = 0,
) -> dict:
    """判定済み候補を、開く順と除外理由に分ける。LLMは呼ばない。"""
    try:
        profile = PROFILES[profile_name]
    except KeyError as e:
        raise ValueError(f"未知の深度プロファイルです: {profile_name}") from e

    verdict_by_url = {verdict.url: verdict for verdict in verdicts}
    missing = [candidate.url for candidate in candidates if candidate.url not in verdict_by_url]
    if missing:
        raise ValueError(f"判定がない候補があります: {', '.join(missing)}")

    rejected = []
    eligible: list[tuple[Candidate, Verdict]] = []
    for candidate in candidates:
        verdict = verdict_by_url[candidate.url]
        if candidate.hop > profile.max_hops:
            rejected.append({"url": candidate.url, "reason": "too_deep"})
        elif verdict.aspect == "none":
            rejected.append({"url": candidate.url, "reason": "off_aspect"})
        else:
            eligible.append((candidate, verdict))

    eligible.sort(key=lambda pair: _rank(pair[1], profile.primary_weight), reverse=True)

    budget_left = max(profile.max_pages - opened_count, 0)
    selected = eligible[:budget_left]
    for candidate, _ in eligible[budget_left:]:
        rejected.append({"url": candidate.url, "reason": "budget"})

    return {
        "open": [candidate.url for candidate, _ in selected],
        "rejected": rejected,
        "diminishing_returns": bool(selected)
        and all(verdict.worth_descending < 0.3 for _, verdict in selected),
        "budget_left": budget_left - len(selected),
    }


def _rank(verdict: "Verdict", primary_weight: float) -> float:
    """relevance だけで並べると、一次資料が入門記事に負ける(実測で確認)。

    公的資料は案件固有の語を含まないため relevance が低く出るが、
    表面情報を排するにはそちらを上に置く必要がある。
    """
    return verdict.relevance + primary_weight * verdict.is_primary
