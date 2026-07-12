# フェーズ1 spec(Agent用要約)

> 正本: `docs/superpowers/specs/medo-design.md`(設計・PRFAQ)。
> このファイルはAgentが作業時に参照する要約。設計変更時は正本を先に更新し、本ファイルを同期する。

## ゴール

What/Why縦切りMVP: **実案件1件で「課題ヒアリング→市場ファクト+フェルミ推定→打ち手ミニPRFAQ比較→合意案の完全版PRFAQ(GCPカタログ根拠付き)」が Claude Code と agy の両ホストで通る**。

## スコープ(フェーズ1でつくるもの)

| コンポーネント | 内容 |
|---|---|
| `medo_core` | RequirementsDoc/Store(背景・理念principles・課題challenges追加、自動バージョン採番・diff)、Fact/FactStore(kind別出典検証・180日stale)、fermi(決定論計算: 四則+累乗、再計算可)、CatalogEntry/Store(出典必須・30日stale・検索)、Artifact/Store(mini-prfaq候補セット/grown_from付きprfaq/fermi、引用ファクト・カタログ込み陳腐化検出)、status(next_step決定論導出)、Storage(LocalJSON+Firestore) |
| `medo` CLI | `requirements save/get/diff`、`facts save/list`、`fermi calc [--from-artifact]`、`catalog search/get`、`artifacts save/get/list`、`status`、`etl run/skus` |
| `medo_etl` | リリースノートBQ公開データセット+Billing Catalog API → Gemini Flash構造化(注入可能) → 検証通過分のみupsert。手動実行。市場ファクトはETL対象外 |
| Skill 3本 | `medo-hearing`(課題・方針の構造化)、`medo-propose-options`(市場ファクト+フェルミ+カタログ根拠→ミニPRFAQ候補セット)、`medo-grow-prfaq`(合意案を完全版PRFAQへ)。共通md→Claude/agy形式にビルド。開始時(ID既知の場合のみ)・終了時に `medo status` で現在地を報告する契約 |

## スコープ外(フェーズ2以降)

make-slides / build-mock / propose-architecture(詳細) / pricing計算機 / decision-roadmap / knowledge-digest / Webアプリ / Scheduler自動化 / MCP / A2A。compare-awsはバックログ

## 不変の契約

1. **事実は縛る**: 保存後の数値の通り道にLLMを挟まない。市場数値・国策・業界動向は出典付きファクト、launch_stage・料金はカタログ値のみ。LLMが数値に触れるのは出典からの初回転記のみ(忠実・無加工)
2. **フェルミ計算はコード**: ast制限の四則演算+累乗のみ。仮定はassume変数として明示(ファクトにしない)
3. **鮮度契約**: カタログ30日・ファクト180日で `stale: true`。Skillは注記義務。引用根拠のstale・欠落は生成物の陳腐化として検出
4. **出典必須**: sources空のカタログエントリ、source空のファクトはバリデーション拒否(market/policy/trendはURL必須)
5. **失敗を推測で補完しない**: CLI失敗=非ゼロ終了+`error:`。ETLは検証通過分のみコミット
6. **課題も要件も確定しない**: 保存は常に新バージョン。生成物は `requirements_version`・`cited_facts`・`cited_catalog_entries` を持ち、prfaqは `grown_from` 必須

## 主要インターフェース(実装の正はコード)

- ストレージパス: `projects/{id}/requirements/v{n}` / `projects/{id}/facts/{fact_id}` / `projects/{id}/artifacts/{type}-v{n}` / `catalog/{service}__{feature}` / `sku_snapshots/{service}`
- ID形式: ファクト `fact-<n>`、カタログ `{service}__{feature}`、生成物 `{type}-v{n}`
- env: `MEDO_BACKEND=local|firestore`、`MEDO_HOME`(local時、既定 `~/.medo`)
