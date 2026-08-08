# 技術スタック

このリポジトリの技術選定・アーキテクチャ方針・コマンド一覧。フェーズ1はSkill+CLIの縦切りMVP。Medo自体はクラウド非依存で、実装手段としてGCPを想定する案件が多い(個人利用・無料枠〜数百円/月)。

---

## 1. アーキテクチャ全体像

```
[ホスト]   Claude Code / agy (Skill+CLI)        簡易Webアプリ(フェーズ2, Gemini)
              │ シェル実行(市場・国策・業界動向・技術ナリッジの検索もホストLLMが担う)
[CLI/コア] medo CLI ── medo_core(要件/ファクト/フェルミ/knowledge/生成物/ストレージ)
              │
[知識層]   Firestore(本番) or ローカルJSON(開発・テスト) + GCS(フェーズ2)
           knowledge/ は既定でMEDO_HOME配下の別gitリポジトリ(案件データと分離、GitHub非公開)
              ↑
[洗練フロー] フェーズ1: ホストLLM検索→CLIが出典検証して保存(facts同様)+git履歴レビュー
           フェーズ2: knowledge-digest(蓄積ナリッジの分析・重複統合。Gemini Flash等で構造化・圧縮)
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

## 3. GCP依存(オプション。medo本体はクラウド非依存)

medo CLI/coreの実行に必須のGCP依存はない(既定バックエンドはローカルJSON)。以下は将来Firestoreを本番ストレージに使う場合・フェーズ2以降でGCPを使う場合の任意依存。

| サービス | 用途 | ライブラリ |
|---|---|---|
| Firestore | 本番ストレージに選ぶ場合(要件・facts・knowledge・生成物) | google-cloud-firestore >= 2.16 |
| Gemini API | (フェーズ2)knowledge-digestでの構造化・圧縮に使う場合 | google-genai >= 1.0 |
| GCS | (フェーズ2)スライド・モック実体 | — |

認証はADC(`gcloud auth application-default login`)。**フェーズ1のknowledge層は自動ETLを持たず、GCPクライアントへの実行時依存は発生しない**(ホストLLM検索+CLI出典検証のみ)。

---

## 4. LLMの使い分け

| 場面 | モデル | 理由 |
|---|---|---|
| ヒアリング・打ち手提案(ミニPRFAQ)・PRFAQ育成・スライド生成 | ホストLLM(Claude Code=Claude / agy=Gemini) | Skillが手順を規定。生成物に `generated_by: claude|gemini` を記録し比較可能 |
| 市場・国策・業界動向・技術ナリッジの検索 | ホストLLMの検索能力 | 取得結果は `medo facts save` / `medo knowledge save` でCLIが出典検証して保存(出典なしは拒否)。数値は出典に忠実に転記し加工しない(換算・集計はfermi) |
| (フェーズ2)knowledge-digestの構造化・圧縮 | Gemini Flash等(注入可能な`generate`関数) | 安価・大量処理。出力は必ずpydantic検証、出典必須 |
| 保存後の数値・フェルミ計算・鮮度 | **LLMを使わない** | コード(CLI/core)が保存・計算・返却する(fermiはast制限の四則演算+累乗のみ) |

---

## 5. 環境変数

| 変数名 | 値 | 用途 |
|---|---|---|
| `MEDO_BACKEND` | `local`(既定) / `firestore` | ストレージバックエンド切替 |
| `MEDO_HOME` | 既定 `~/.medo` | localバックエンドのルートディレクトリ(knowledge/もこの配下、既定で別gitリポジトリ) |
| `GOOGLE_CLOUD_PROJECT` | GCPプロジェクトID | Firestoreを使う場合のみ |
| `GEMINI_API_KEY` | (ADCを使わない場合) | フェーズ2 knowledge-digestで使う場合のみ |

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
uv run medo knowledge search "<キーワード>"        # 案件横断の技術ナリッジ(出典・stale付き)
uv run medo knowledge save --project <id> --statement "..." --source "..."  # 案件固有ナレッジ(単一案件スコープ・出典URL不要)
uv run medo status --project <id>   # 現在地(要件・ファクト・生成物・next_step)

# Skillビルドと配布(3ホスト共通のSKILL.md形式)
python skills/build.py
cp -r skills/dist/* ~/.claude/skills/   # Claude Code(ユーザーレベル)
cp -r skills/dist/* ~/.codex/skills/    # Codex CLI(ユーザーレベル)
cp -r skills/dist/* .agents/skills/     # agy(プロジェクトレベル。リポジトリ直下から自動検出)
```

---

## 7. テスト方針

| 対象 | 方法 |
|---|---|
| core(スキーマ・バージョニング・鮮度判定) | ユニットテスト(LocalJsonStorage + tmp_path) |
| CLI | typer.testing.CliRunner(env: MEDO_BACKEND=local, MEDO_HOME=tmp) |
| pricing計算機(フェーズ2) | 公式Pricing Calculatorとの突合ゴールデンテスト |
| knowledge-digest(フェーズ2) | LLM構造化はMagicMockまたは注入可能なgenerate関数で分離。LLM実呼び出しをテストに含めない |
| Skill | 実案件1件のevalケース(同一要件→提案の安定性を目視確認) |
| 実環境スモーク | フェーズ1 Task 10(手動。Firestoreを使う場合のみGCP認証が絡む) |

CIはフェーズ1では構築しない。ローカルで `uv run pytest` を実行。

---

## 8. セキュリティ・コスト

- 個人利用前提: 認証・マルチテナントなし(チーム展開はバックログ)
- シークレット: `.env*` や `settings.local.json` は `.gitignore` で除外
- ランニングコスト目安: 既定(ローカルJSON)は無料。Firestore/GCS等を使う場合も無料枠内〜数百円/月。ホストLLMは既存契約内
