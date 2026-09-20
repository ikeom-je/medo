"""深掘り調査の計画を決定論的に組み立てる。"""

from pydantic import BaseModel

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
    prefer_primary: bool
    aspects: tuple[str, ...]


_ALL_ASPECTS = tuple(ASPECTS)

PROFILES = {
    "scan": DepthProfile(
        name="scan",
        max_hops=1,
        max_pages=5,
        prefer_primary=False,
        aspects=("actor_org", "market"),
    ),
    "structural": DepthProfile(
        name="structural",
        max_hops=3,
        max_pages=20,
        prefer_primary=False,
        aspects=_ALL_ASPECTS,
    ),
    "deep": DepthProfile(
        # 一次資料はポータル→検索→一覧→詳細→PDFと辿るため、3階層では届かない。
        name="deep",
        max_hops=6,
        max_pages=60,
        prefer_primary=True,
        aspects=_ALL_ASPECTS,
    ),
}

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
        "findings_to_resolve": findings_to_resolve,
    }
