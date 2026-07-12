# 技術スタック

このリポジトリの技術選定・アーキテクチャ方針・コマンド一覧。フェーズ1はSkill+CLIの縦切りMVP、運用はGCP上(個人利用・無料枠〜数百円/月)。

---

## 1. アーキテクチャ全体像

```
[ホスト]   Claude Code / agy (Skill+CLI)        簡易Webアプリ(フェーズ2, Gemini)
              │ シェル実行(市場・国策・業界動向の検索もホストLLMが担う)
[CLI/コア] medo CLI ── medo_core(要件/ファクト/フェルミ/カタログ/生成物/ストレージ)
              │
[知識層]   Firestore(本番) or ローカルJSON(開発・テスト) + GCS(フェーズ2)
              ↑
[ETL]      GCPカタログのみ手動実行(フェーズ1) → Scheduler+Cloud Run Job(フェーズ3):
           リリースノートBQ公開データセット + Billing Catalog API
           → Gemini Flashで構造化 → 検証通過分のみコミット
           (市場ファクトはETLしない: 案件毎にホストLLM検索→CLIが出典検証して保存)
```

---

## 2. 言語・ツールチェーン

| 領域 | 技術 | 備考 |
|---|---|---|
| 言語 | Python 3.12+ | |
| パッケージ管理 | **uv**(uv workspace) | モノレポ: core / cli / etl |
| スキーマ・検証 | pydantic >= 2.7 | 全ドメインモデル。LLM出力の検証にも使う |
| CLI | typer >= 0.12 | console_script: `medo` |
| テスト | pytest >= 8 | ルート pyproject.toml の testpaths で全パッケージ横断 |
| リント | ruff(line-length 100) | |
| ビルドバックエンド | hatchling | 各パッケージ共通 |

---

## 3. GCP依存

| サービス | 用途 | ライブラリ |
|---|---|---|
| Firestore | 本番ストレージ(要件・カタログ・生成物) | google-cloud-firestore >= 2.16 |
| BigQuery | リリースノート公開データセット `bigquery-public-data.google_cloud_release_notes.release_notes` | google-cloud-bigquery >= 3.25 |
| Cloud Billing Catalog API | SKUスナップショット(金額はカタログに焼き込まない) | google-cloud-billing >= 1.13 |
| Gemini API | ETL構造化・(フェーズ2)knowledge-digest。**構造化・圧縮専任** | google-genai >= 1.0 |
| Cloud Run Job + Scheduler | (フェーズ3)ETL自動化 | — |
| GCS | (フェーズ2)スライド・モック実体 | — |

認証はADC(`gcloud auth application-default login`)。

---

## 4. LLMの使い分け

| 場面 | モデル | 理由 |
|---|---|---|
| ヒアリング・打ち手提案(ミニPRFAQ)・PRFAQ育成・スライド生成 | ホストLLM(Claude Code=Claude / agy=Gemini) | Skillが手順を規定。生成物に `generated_by: claude|gemini` を記録し比較可能 |
| 市場・国策・業界動向の検索 | ホストLLMの検索能力 | 取得結果は `medo facts save` でCLIが出典検証して保存(出典なしは拒否)。数値は出典に忠実に転記し加工しない(換算・集計はfermi) |
| ETL構造化・knowledge-digest | Gemini Flash(`gemini-flash-latest`) | 安価・大量処理。出力は必ずpydantic検証、出典必須 |
| 保存後の数値・フェルミ計算・launch_stage・鮮度 | **LLMを使わない** | コード(CLI/core)が保存・計算・返却する(fermiはast制限の四則演算+累乗のみ) |

---

## 5. 環境変数

| 変数名 | 値 | 用途 |
|---|---|---|
| `MEDO_BACKEND` | `local`(既定) / `firestore` | ストレージバックエンド切替 |
| `MEDO_HOME` | 既定 `~/.medo` | localバックエンドのルートディレクトリ |
| `GOOGLE_CLOUD_PROJECT` | GCPプロジェクトID | Firestore / BigQuery / Billing |
| `GEMINI_API_KEY` | (ADCを使わない場合) | google-genai |

---

## 6. 開発コマンド

```bash
# 依存解決(全パッケージ)
uv sync --all-packages

# テスト(全パッケージ横断)
uv run pytest

# リント
uv run ruff check .

# CLI実行
uv run medo --help
uv run medo requirements get --project <id> --format json
uv run medo facts list --project <id>            # 市場・国策・業界動向・個社ファクト(出典・stale付き)
uv run medo fermi calc --project <id> --file <model.yaml>  # フェルミ推定(コードが計算)
uv run medo catalog search "<キーワード>"
uv run medo status --project <id>   # 現在地(要件・ファクト・生成物・next_step)

# ETL(手動、GCP認証必須)
MEDO_BACKEND=local uv run medo etl run --since 2026-06-01 --services vertex-ai --dry-run
uv run medo etl skus --service vertex-ai

# Skillビルドと配布
python skills/build.py
cp -r skills/dist/claude/* ~/.claude/skills/     # Claude Code
# agy: skills/dist/agy/*.md をAGENTS.mdから参照
```

---

## 7. テスト方針

| 対象 | 方法 |
|---|---|
| core(スキーマ・バージョニング・鮮度判定) | ユニットテスト(LocalJsonStorage + tmp_path) |
| CLI | typer.testing.CliRunner(env: MEDO_BACKEND=local, MEDO_HOME=tmp) |
| ETL | BQ/Billing/GeminiはMagicMockまたは注入可能なgenerate関数で分離。LLM実呼び出しをテストに含めない |
| pricing計算機(フェーズ2) | 公式Pricing Calculatorとの突合ゴールデンテスト |
| Skill | 実案件1件のevalケース(同一要件→提案の安定性を目視確認) |
| 実環境スモーク | フェーズ1 Task 10(手動。GCP認証・課金が絡むため自動化しない) |

CIはフェーズ1では構築しない。ローカルで `uv run pytest` を実行。

---

## 8. セキュリティ・コスト

- 個人利用前提: 認証・マルチテナントなし(チーム展開はバックログ)
- シークレット: `.env*` や `settings.local.json` は `.gitignore` で除外
- ランニングコスト目安: Firestore/GCS/Cloud Run 無料枠内〜数百円/月 + Gemini Flash 数百円/月。ホストLLMは既存契約内
