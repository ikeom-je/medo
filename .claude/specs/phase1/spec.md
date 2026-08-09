# フェーズ1 spec(Agent用要約)

> 正本: `docs/superpowers/specs/medo-design.md`(設計・PRFAQ)。
> このファイルはAgentが作業時に参照する要約。設計変更時は正本を先に更新し、本ファイルを同期する。

## ゴール

What/Why縦切りMVP: **実案件1件で「課題ヒアリング→市場ファクト+フェルミ推定→打ち手ミニPRFAQ比較→合意案の完全版PRFAQ(技術ナレッジ根拠付き)」が Claude Code と agy の両ホストで通る**。

## スコープ(フェーズ1でつくるもの)

| コンポーネント | 内容 |
|---|---|
| `medo_core` | RequirementsDoc/Store(背景・理念principles・課題challenges・knowledge_backend追加、自動バージョン採番・diff)、Fact/FactStore(kind別出典検証・180日stale)、fermi(決定論計算: 四則+累乗、再計算可)、KnowledgeEntry/Store(案件横断技術ナレッジ・出典必須・kind別stale)+ProjectKnowledgeEntry/Backend(案件固有ナレッジ・markdown/sqlite選択)、Artifact/Store(mini-prfaq候補セット/grown_from付きprfaq/fermi、引用ファクト・ナレッジ込み陳腐化検出)、status(next_step決定論導出)、Storage(LocalJSON+Firestore) |
| `medo` CLI | `requirements save/get/diff`、`facts save/list`、`fermi calc [--from-artifact]`、`knowledge search/get/save`、`artifacts save/get/list`、`status` |
| Skill 3本 | `medo-hearing`(課題・方針の構造化)、`medo-propose-options`(市場ファクト+フェルミ+ナレッジ根拠→ミニPRFAQ候補セット)、`medo-grow-prfaq`(合意案を完全版PRFAQへ)。共通SKILL.md(1フォルダ=1 Skill)→Claude/Codex/agy共通形式にビルド。開始時(ID既知の場合のみ)・終了時に `medo status` で現在地を報告し、対話から得た案件固有ノウハウがあれば `medo knowledge save --project` で追記する契約 |

## スコープ外(フェーズ2以降)

make-slides / build-mock / propose-architecture(詳細) / pricing計算機 / decision-roadmap / knowledge-digest / Webアプリ / Scheduler自動化 / MCP / A2A。compare-awsはバックログ

## 不変の契約

1. **事実は縛る**: 保存後の数値の通り道にLLMを挟まない。市場数値・国策・業界動向は出典付きファクト、技術/サービス情報は技術ナレッジ値のみ。LLMが数値に触れるのは出典からの初回転記のみ(忠実・無加工)
2. **フェルミ計算はコード**: ast制限の四則演算+累乗のみ。仮定はassume変数として明示(ファクトにしない)
3. **鮮度契約**: 技術ナレッジ(kind=tech)30日・ファクト/他ナレッジ180日で `stale: true`。Skillは注記義務。引用根拠のstale・欠落は生成物の陳腐化として検出
4. **出典必須**: source空の技術ナレッジ・ファクトはバリデーション拒否(market/policy/trend/techはURL必須。案件固有ナレッジは対話メモ可)
5. **失敗を推測で補完しない**: CLI失敗=非ゼロ終了+`error:`
6. **課題も要件も確定しない**: 保存は常に新バージョン。生成物は `requirements_version`・`cited_facts`・`cited_knowledge` を持ち、prfaqは `grown_from` 必須
7. **クラウド非依存**: 自動ETL(特定クラウドAPIへの常設依存)は採用しない。技術ナレッジはホストLLMが都度検索しCLIが出典検証して保存する
8. **表現の分担**: コード=How / テストコード=What / コミットログ=Why / コードコメント=Why not(workflow.md Section 4)

## 主要インターフェース(実装の正はコード)

- ストレージパス: `projects/{id}/requirements/v{n}` / `projects/{id}/facts/{fact_id}` / `projects/{id}/artifacts/{type}-v{n}` / `knowledge/{kind}/{entry_id}` / `knowledge/projects/{project_id}/{entry_id}`
- ID形式: ファクト `fact-<n>`、技術ナレッジ `{kind}-<n>`、生成物 `{type}-v{n}`
- env: `MEDO_BACKEND=local|firestore`、`MEDO_HOME`(local時、既定 `~/.medo`)
