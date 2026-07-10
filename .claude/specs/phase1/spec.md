# フェーズ1 spec(Agent用要約)

> 正本: `docs/superpowers/specs/2026-07-05-medo-design.md`(設計・PRFAQ)。
> このファイルはAgentが作業時に参照する要約。設計変更時は正本を先に更新し、本ファイルを同期する。

## ゴール

縦切りMVP: **実案件1件で「ヒアリング→要件保存→根拠付きアーキ案生成」が Claude Code と agy の両ホストで通る**。

## スコープ(フェーズ1でつくるもの)

| コンポーネント | 内容 |
|---|---|
| `medo_core` | RequirementsDoc/Store(自動バージョン採番・diff)、CatalogEntry/Store(出典必須・30日stale判定・検索)、Artifact/Store(要件バージョン紐づけ・陳腐化検出)、Storage(LocalJSON+Firestore) |
| `medo` CLI | `requirements save/get/diff`、`catalog search/get`、`artifacts save/list`、`status`(現在地とnext_stepの決定論導出)、`etl run/skus` |
| `medo_etl` | リリースノートBQ公開データセット+Billing Catalog API → Gemini Flash構造化(注入可能) → 検証通過分のみupsert。手動実行 |
| Skill 2本 | `medo-hearing`(アイデア→要件抽出)、`medo-propose-architecture`(根拠付き複数案)。共通md→Claude/agy形式にビルド。開始時(プロジェクトID既知の場合のみ)・終了時に `medo status` で現在地を報告する契約 |

## スコープ外(フェーズ2以降)

pricing計算機 / make-slides / build-mock / compare-aws / decision-roadmap / knowledge-digest / Webアプリ / Scheduler自動化 / MCP / A2A

## 不変の契約

1. **事実は縛る**: launch_stage・鮮度・料金の通り道にLLMを挟まない。提案が引用する事実はカタログ値のみ
2. **鮮度契約**: `last_verified` 30日超 → `stale: true` を付与、Skillは注記義務
3. **出典必須**: sources空のカタログエントリはバリデーション拒否
4. **失敗を推測で補完しない**: CLI失敗=非ゼロ終了+`error:`。ETLは検証通過分のみコミット
5. **要件は確定しない**: 保存は常に新バージョン。生成物は `requirements_version` と `cited_catalog_entries` を必ず持つ

## 主要インターフェース(実装の正はコード)

- ストレージパス: `projects/{id}/requirements/v{n}` / `projects/{id}/artifacts/{type}-v{n}` / `catalog/{service}__{feature}` / `sku_snapshots/{service}`
- カタログエントリID: `{service}__{feature}`(例: `vertex-ai__context-caching`)
- env: `MEDO_BACKEND=local|firestore`、`MEDO_HOME`(local時、既定 `~/.medo`)
