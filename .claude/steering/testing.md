# テストルール

Medo のテスト方針。フェーズ1実装計画(`docs/superpowers/plans/medo-phase1.md`)の各Taskは TDD(失敗テスト→実装→パス確認)で進める。

---

## 1. テストピラミッド

```
     実環境スモーク(手動・フェーズ1 Task 10)
    /                                      \
   Skill evalケース(実案件1件・目視で安定性確認)
  /                                          \
 ユニット+CLIテスト(pytest) ← ここが主体。高速・決定論・GCP非依存
```

CI はフェーズ1では構築しない。ローカルで `uv run pytest` を実行してからコミットする。

---

## 2. テストタイプ

### ユニットテスト(core / etl)

- 場所: `core/tests/`、`etl/tests/`(パッケージごと)
- 実行: `uv run pytest` (全体) / `uv run pytest core/tests/test_catalog.py -v` (個別)
- ストレージは `LocalJsonStorage(tmp_path)` を使う。Firestoreの実接続はテストしない(薄いラッパーは MagicMock でマッピングだけ検証)

### CLIテスト

- 場所: `cli/tests/test_cli.py`
- `typer.testing.CliRunner` + autouse fixture で `MEDO_BACKEND=local` / `MEDO_HOME=tmp_path` を設定
- 正常系の出力形式(`saved: v1` 等)と、失敗系(存在しないプロジェクト→exit code 1 + `error:`)の両方を必ず書く

### ETLの外部依存の切り方

| 依存 | テストでの扱い |
|---|---|
| BigQuery / Billing クライアント | MagicMock(発行するクエリ文字列・呼び出し引数を検証) |
| Gemini(構造化) | `generate: Callable[[str], str]` を注入。fakeがJSONを返す |
| **LLMの実呼び出し** | **テストに含めない**(コスト・非決定性のため) |

LLM出力の検証ロジック(pydantic検証・不正JSON・不正launch_stage)は fake generate で必ずカバーする。

### Skill evalケース

- Skillは自動テスト不能(ホストLLMが実行する手順書)なので、実案件1件を evalケースとして固定し、同一要件→提案の安定性(引用エントリIDの一致・構成の一貫性)を目視確認する
- Skill本文を変更したら evalケースを再実行する

### 実環境スモーク(手動)

- GCP認証・課金が絡むため自動化しない。手順はフェーズ1計画 Task 10 と `docs/setup.md`(スモーク後に作成)を参照

---

## 3. フェーズ2で追加するテスト

| 対象 | 方法 |
|---|---|
| pricing計算機 | 公式Pricing Calculatorとの突合ゴールデンテスト(代表構成数パターン) |
| ETLスナップショット | リリースノートのサンプル固定でGemini構造化の出力スキーマ検証 |
| カタログ品質 | 出典URL生存チェック(リンク切れ検出) |

---

## 4. テストの書き方

- テスト名は挙動を表す: `test_stale_when_older_than_30_days`(◯) / `test_catalog_2`(✕)
- 1テスト1検証事項。Arrange(準備)→Act(実行)→Assert(検証)
- 日付依存のテストは `today` を引数注入して固定する(`date.today()` をテスト内で直接踏まない)
- fixtureはヘルパー関数(`_doc(**kw)` / `_entry(**kw)`)でデフォルト+上書きの形にする
- 実装の詳細(内部の呼び出し回数等)ではなく、外から見える挙動(保存結果・出力・終了コード)をテストする

---

## 5. コミット前

```bash
uv run pytest          # 全テスト
uv run ruff check .    # リント
```

テストが失敗したままコミットしない。「テストが通った」と主張する前に必ず実行結果を確認する。
