# プロジェクト構造

ディレクトリ構造・命名規則・モジュール責務。新規ファイルを置く場所に迷ったら本ファイルを参照する。
(フェーズ1実装計画: `docs/superpowers/plans/medo-phase1.md` に準拠。未実装の部分は計画上の構造)

---

## 1. ルートディレクトリ

uv workspace によるPythonモノレポ構成。

```
medo/
├── .claude/             # Agent用ドキュメント(要約とポインタ。正本はdocs/)
│   ├── steering/        #   常時参照する規約: product / tech / structure / testing / workflow / git
│   ├── specs/           #   フェーズ単位のAgent向けspec要約(例: phase1/{spec,tasks}.md)
│   └── settings.local.json  # ローカル設定(.gitignored)
├── docs/                # 人間用ドキュメント(正本)
│   └── superpowers/
│       ├── specs/       # 設計ドキュメント(PRFAQ含む)
│       └── plans/       # 実装計画
├── core/                # medo-core: ホスト非依存ドメインロジック
├── cli/                 # medo-cli: `medo` コマンド
├── skills/              # Skill本文(共通md)とビルドスクリプト
├── webapp/              # (フェーズ2) 簡易対話クライアント兼MCP/A2A動作確認用
├── pyproject.toml       # workspace ルート(pytest/ruff設定)
└── uv.lock
```

将来追加(バックログ): `mcp-server/`(coreの薄いMCPアダプタ)、`a2a-server/`(Gemini Enterprise接続)。

---

## 2. `core/` — medo-core(決定論層の中心)

```
core/
├── pyproject.toml
├── src/medo_core/
│   ├── config.py        # get_storage(): env MEDO_BACKEND/MEDO_HOME でバックエンド選択
│   ├── storage.py       # Storage Protocol + LocalJsonStorage + FirestoreStorage
│   ├── requirements.py  # RequirementsDoc(背景・方針/理念・課題・要件)+ Store(自動バージョン採番・diff)
│   ├── facts.py         # Fact + FactStore(kind: market/policy/trend/company。案件スコープ・出典必須・180日stale判定)
│   ├── fermi.py         # フェルミ推定の決定論計算(ファクト参照+明示的仮定×式。ast制限の四則演算+累乗。モデル込み保存で再計算可能)
│   ├── knowledge.py     # KnowledgeEntry + KnowledgeStore(factsと同型・案件横断・出典必須) + ProjectKnowledgeEntry + KnowledgeBackend(markdown/sqlite。案件固有・単一案件スコープ)
│   ├── artifacts.py     # Artifact + ArtifactStore(要件バージョン・引用ファクト/ナリッジ紐づけ・陳腐化検出)
│   └── status.py        # project_status(): 現在地と次ステップ(next_step)の決定論導出
└── tests/
```

**責務**: 要件・ファクト・フェルミ計算・技術ナリッジ・生成物のスキーマと永続化・決定論計算。LLM呼び出しを含まない(唯一の例外は将来の knowledge-digest = 構造化・圧縮専任)。

---

## 3. `cli/` — medo-cli

```
cli/
├── pyproject.toml       # console_script: medo
├── src/medo_cli/
│   └── main.py          # typer app: requirements / facts / fermi / knowledge / artifacts / status
└── tests/
```

**責務**: coreをホストLLM(Skill経由)に公開する決定論的インターフェース。失敗時は非ゼロ終了+`error: <理由>`(stderr)。推測で補完しない。

---

## 4. `skills/` — Skill配布物

```
skills/
├── src/                 # 共通md(frontmatter付き)。1ファイル=1 Skill
│   ├── hearing.md            # 業界・ビジネス状況・課題・経営思想/方針の構造化
│   ├── propose-options.md    # 市場ファクト+フェルミ+技術ナリッジ根拠→打ち手候補のミニPRFAQ候補セット化
│   └── grow-prfaq.md         # 合意案を完全版PRFAQへ育成(技術ナリッジ根拠)
├── build.py             # dist/claude/<name>/SKILL.md と dist/agy/<name>.md を生成
├── tests/
└── dist/                # ビルド出力(.gitignored)
```

- Skill本文は `src/` の1箇所で管理し、ホスト形式へは `build.py` の薄い変換のみ
- Claude Code へは `~/.claude/skills/` にコピー、agy へは `dist/agy/*.md` をAGENTS.mdから参照

---

## 5. ストレージパス設計(Firestore互換)

document=偶数セグメント、collection=奇数セグメント。LocalJsonStorage も同じパスをファイルにマップする。

| パス | 内容 |
|---|---|
| `projects/{id}/requirements/v{n}` | 要件ドキュメント(背景・方針/理念・課題・要件。旧版保持) |
| `projects/{id}/facts/{fact_id}` | 市場・国策・業界動向・個社ファクト(案件スコープ・出典必須) |
| `projects/{id}/artifacts/{type}-v{n}` | 生成物(type別バージョン採番。mini-prfaq/prfaq/fermi/comparison/architecture/slides/mock) |
| `knowledge/{kind}/{entry_id}` | 技術ナリッジ(案件横断スコープ・出典必須。既定でMEDO_HOME配下の別gitリポジトリ) |
| `knowledge/projects/{project_id}/{entry_id}` | 案件固有ナレッジ(単一案件スコープ・出典URL不要。同じgitリポジトリ内。バックエンドはmarkdown\|sqliteを案件ごとに選択) |

---

## 6. 命名規則

| 種別 | 形式 | 例 |
|---|---|---|
| Pythonパッケージ | `medo_<name>`(snake_case) | `medo_core` |
| pipパッケージ名 | `medo-<name>`(kebab-case) | `medo-core` |
| モジュール・関数・変数 | `snake_case` | `fetch_release_notes` |
| クラス・pydanticモデル | `PascalCase` | `KnowledgeEntry` |
| 定数 | `SCREAMING_SNAKE_CASE` | `STALE_THRESHOLD_DAYS` |
| テスト | `test_<module>.py` / `test_<挙動>` | `test_facts.py::test_stale_when_older_than_180_days` |
| Skill名 | `medo-<name>`(kebab-case) | `medo-hearing` |
| ナリッジエントリID | `{kind}-{n}` | `tech-1` |
| 日付 | ISO文字列 `YYYY-MM-DD` | `retrieved: "2026-07-01"` |

---

## 7. 依存方向

```
[skills/] ──(CLI呼び出し手順を記述)──▶ [cli/] ──▶ [core/]
[webapp/(フェーズ2)] ──▶ [core/]
```

- `core/` は他パッケージに依存しない(ドメインロジックの独立性)
- `cli/` は core のみに依存。Skillとの契約(コマンド体系・出力形式)を壊す変更は Skill本文も同時に更新する
- 逆流(core → cli 等)は禁止

---

## 8. 新規ファイルを置く場所のガイド

| 何を作りたいか | 置く場所 |
|---|---|
| 新しいドメイン概念(スキーマ+ストア) | `core/src/medo_core/<name>.py` + `core/tests/test_<name>.py` |
| 新しいCLIサブコマンド | `cli/src/medo_cli/main.py`(肥大化したら `commands/<name>.py` に分割) |
| 新しいSkill | `skills/src/<name>.md`(frontmatter必須) → `build.py` が自動で両形式に変換 |
| 設計変更 | 正本 `docs/superpowers/specs/` を更新 → `.claude/steering/` と `.claude/specs/` の要約を同期 |
| 人間向け説明・手順 | `docs/`(例: `docs/setup.md`) |
| Agent向け規約・要約 | `.claude/steering/` または `.claude/specs/<phase>/` |
