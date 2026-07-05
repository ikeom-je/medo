# プロジェクト構造

ディレクトリ構造・命名規則・モジュール責務。新規ファイルを置く場所に迷ったら本ファイルを参照する。
(フェーズ1実装計画: `docs/superpowers/plans/2026-07-05-medo-phase1.md` に準拠。未実装の部分は計画上の構造)

---

## 1. ルートディレクトリ

uv workspace によるPythonモノレポ構成。

```
ag-arch-agent/
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
├── etl/                 # medo-etl: カタログ更新パイプライン
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
│   ├── requirements.py  # RequirementsDoc + RequirementsStore(自動バージョン採番・diff)
│   ├── catalog.py       # CatalogEntry + CatalogStore(出典必須・30日stale判定・検索)
│   └── artifacts.py     # Artifact + ArtifactStore(要件バージョン紐づけ・陳腐化検出)
└── tests/
```

**責務**: 要件・カタログ・生成物のスキーマと永続化。LLM呼び出しを含まない(唯一の例外は将来の `knowledge/` = digest専任)。

---

## 3. `cli/` — medo-cli

```
cli/
├── pyproject.toml       # console_script: medo
├── src/medo_cli/
│   └── main.py          # typer app: requirements / catalog / artifacts / etl
└── tests/
```

**責務**: coreをホストLLM(Skill経由)に公開する決定論的インターフェース。失敗時は非ゼロ終了+`error: <理由>`(stderr)。推測で補完しない。

---

## 4. `etl/` — medo-etl

```
etl/
├── pyproject.toml
├── services.yaml        # カタログ対象サービスリスト(AI/ML重点+定番)
├── src/medo_etl/
│   ├── release_notes.py # BQ公開データセット(google_cloud_release_notes)からの取得
│   ├── structure.py     # Gemini Flash構造化(generate関数は注入可能)+検証
│   ├── skus.py          # Billing Catalog APIからのSKUスナップショット
│   └── pipeline.py      # 取得→構造化→検証→upsert。通過分のみコミット
└── tests/
```

---

## 5. `skills/` — Skill配布物

```
skills/
├── src/                 # 共通md(frontmatter付き)。1ファイル=1 Skill
│   ├── hearing.md
│   └── propose-architecture.md
├── build.py             # dist/claude/<name>/SKILL.md と dist/agy/<name>.md を生成
├── tests/
└── dist/                # ビルド出力(.gitignored)
```

- Skill本文は `src/` の1箇所で管理し、ホスト形式へは `build.py` の薄い変換のみ
- Claude Code へは `~/.claude/skills/` にコピー、agy へは `dist/agy/*.md` をAGENTS.mdから参照

---

## 6. ストレージパス設計(Firestore互換)

document=偶数セグメント、collection=奇数セグメント。LocalJsonStorage も同じパスをファイルにマップする。

| パス | 内容 |
|---|---|
| `projects/{id}/requirements/v{n}` | 要件ドキュメント(旧版保持) |
| `projects/{id}/artifacts/{type}-v{n}` | 生成物(type別バージョン採番) |
| `catalog/{service}__{feature}` | カタログエントリ(論理ID `{service}/{feature}` を平坦化) |
| `sku_snapshots/{service}` | SKUスナップショット(1サービス1ドキュメント) |

---

## 7. 命名規則

| 種別 | 形式 | 例 |
|---|---|---|
| Pythonパッケージ | `medo_<name>`(snake_case) | `medo_core` |
| pipパッケージ名 | `medo-<name>`(kebab-case) | `medo-core` |
| モジュール・関数・変数 | `snake_case` | `fetch_release_notes` |
| クラス・pydanticモデル | `PascalCase` | `CatalogEntry` |
| 定数 | `SCREAMING_SNAKE_CASE` | `STALE_THRESHOLD_DAYS` |
| テスト | `test_<module>.py` / `test_<挙動>` | `test_catalog.py::test_stale_when_older_than_30_days` |
| Skill名 | `medo-<name>`(kebab-case) | `medo-hearing` |
| サービスslug | kebab-case(services.yaml準拠) | `vertex-ai` |
| カタログエントリID | `{service}__{feature}` | `vertex-ai__context-caching` |
| 日付 | ISO文字列 `YYYY-MM-DD` | `last_verified: "2026-07-01"` |

---

## 8. 依存方向

```
[skills/] ──(CLI呼び出し手順を記述)──▶ [cli/] ──▶ [core/]
[etl/] ──▶ [core/]
[webapp/(フェーズ2)] ──▶ [core/]
```

- `core/` は他パッケージに依存しない(ドメインロジックの独立性)
- `cli/` は core と etl のみに依存。Skillとの契約(コマンド体系・出力形式)を壊す変更は Skill本文も同時に更新する
- 逆流(core → cli 等)は禁止

---

## 9. 新規ファイルを置く場所のガイド

| 何を作りたいか | 置く場所 |
|---|---|
| 新しいドメイン概念(スキーマ+ストア) | `core/src/medo_core/<name>.py` + `core/tests/test_<name>.py` |
| 新しいCLIサブコマンド | `cli/src/medo_cli/main.py`(肥大化したら `commands/<name>.py` に分割) |
| 新しいETLソース | `etl/src/medo_etl/<source>.py` + services.yaml 更新 |
| 新しいSkill | `skills/src/<name>.md`(frontmatter必須) → `build.py` が自動で両形式に変換 |
| 設計変更 | 正本 `docs/superpowers/specs/` を更新 → `.claude/steering/` と `.claude/specs/` の要約を同期 |
| 人間向け説明・手順 | `docs/`(例: `docs/setup.md`) |
| Agent向け規約・要約 | `.claude/steering/` または `.claude/specs/<phase>/` |
