"""Gemini Flashによる構造化(生成的だが出典・検証必須)。generate関数は注入可能。"""

import json
from typing import Callable

from medo_core.catalog import CatalogEntry
from medo_etl.release_notes import ReleaseNote, ServiceConfig

PROMPT_TEMPLATE = """\
あなたはGoogle Cloudのリリースノートを機能カタログに構造化する係です。
以下のリリースノート群から、アーキテクチャ検討に有用な「機能」単位のエントリを抽出し、
JSON配列のみを出力してください。各要素のスキーマ:
{{"feature": "kebab-case-slug", "launch_stage": "GA|Preview|Deprecated",
  "since": "YYYY-MM-DD または null", "summary": "日本語で1〜2文", "caveats": ["注意点", ...]}}

規則:
- launch_stageはノート本文の記述(GA/generally available/Preview/deprecated)から判定する
- 判定できない情報は捏造せず、その項目を出力しない
- 修正のみのノート(FIX)はスキップしてよい

対象サービス: {product_name}

リリースノート:
{notes}
"""


def structure_notes(
    service: ServiceConfig,
    notes: list[ReleaseNote],
    generate: Callable[[str], str],
    today: str,
) -> tuple[list[CatalogEntry], list[str]]:
    notes_text = "\n".join(
        f"- [{n.release_note_type}] ({n.published_at}) {n.description}" for n in notes
    )
    prompt = PROMPT_TEMPLATE.format(product_name=service.product_name, notes=notes_text)
    raw = generate(prompt)

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        return [], [f"{service.slug}: LLM出力がJSONとして不正: {e}"]

    if not isinstance(items, list):
        return [], [f"{service.slug}: LLM出力がJSON配列ではありません: {type(items).__name__}"]

    entries: list[CatalogEntry] = []
    errors: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            errors.append(f"{service.slug}: 配列要素がオブジェクトではありません: {item!r}")
            continue
        try:
            entries.append(
                CatalogEntry(
                    service=service.slug,
                    feature=item.get("feature", ""),
                    launch_stage=item.get("launch_stage"),
                    since=item.get("since"),
                    summary=item.get("summary", ""),
                    caveats=item.get("caveats", []),
                    sources=[service.release_notes_url],
                    last_verified=today,
                )
            )
        except Exception as e:  # pydantic.ValidationError
            errors.append(f"{service.slug}/{item.get('feature', '?')}: 検証エラー: {e}")
    return entries, errors


def gemini_generate(model: str = "gemini-flash-latest") -> Callable[[str], str]:
    """本番用generate。google-genaiクライアントを遅延生成する。"""
    from google import genai

    client = genai.Client()

    def generate(prompt: str) -> str:
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return resp.text

    return generate
