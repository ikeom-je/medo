# テストルール

Medo のテスト方針。フェーズ1実装計画(`docs/superpowers/plans/medo-phase1.md`)の各Taskは TDD(失敗テスト→実装→パス確認)で進める。

---

## 1. テストピラミッド

```
     実環境スモーク(手動・フェーズ1 Task 10)
    /                                      \
   Skill evalケース(実案件1件・目視で安定性確認)
  /                                          \
 ユニット+CLIテスト(pytest) ← ここが主体。高速・決定論・クラウド非依存
```

CI はフェーズ1では構築しない。ローカルで `uv run pytest` を実行してからコミットする。

---

## 2. テストタイプ

### ユニットテスト(core)

- 場所: `core/tests/`
- 実行: `uv run pytest` (全体) / `uv run pytest core/tests/test_knowledge.py -v` (個別)
- ストレージは `LocalJsonStorage(tmp_path)` を使う。Firestoreの実接続はテストしない(薄いラッパーは MagicMock でマッピングだけ検証)

### CLIテスト

- 場所: `cli/tests/test_cli.py`
- `typer.testing.CliRunner` + autouse fixture で `MEDO_BACKEND=local` / `MEDO_HOME=tmp_path` を設定
- 正常系の出力形式(`saved: v1` 等)と、失敗系(存在しないプロジェクト→exit code 1 + `error:`)の両方を必ず書く

### 外部の判定(Jev)の切り方

| 依存 | テストでの扱い |
|---|---|
| Jev(TypeSafe System One) | `cli/src/medo_cli/jev.py` の `urlopen`、または呼び出し側の関数(`judge_pairs` 等)を差し替える。core は Jev を呼ばないので差し替え不要 |
| **Jevの実呼び出し** | **テストに含めない**(コスト・非決定性のため)。閾値や質問文の良し悪しは `scripts/eval/` の正解付き評価セットで実呼び出しして測る |

鍵が無いとき(`unavailable`)、呼び出し・応答の解析が失敗したとき(非ゼロ終了)、応答の欠けや型違いは、差し替えた偽物で必ずカバーする。

**評価セットの分け方**: 正解付きの評価セットは、閾値や質問文を決める**調整用**(tune)と、受け入れを判定する**検証用**(validate)に分ける。検証用の結果を見て閾値や質問文を直したら、その組はもう独立した検証ではない。**調整に一度も使っていない新しい組**(holdout。質問文を見ていない人かモデルに作らせる)で1回だけ評価し直す。holdout も結果を見て直したら、また新しい組が要る

### Skill evalケース

- Skillは自動テスト不能(ホストLLMが実行する手順書)なので、実案件1件を evalケースとして固定し、同一要件→提案の安定性(引用エントリIDの一致・構成の一貫性)を目視確認する
- Skill本文を変更したら evalケースを再実行する

### 実環境スモーク(手動)

- クラウド認証・課金が絡むため自動化しない。手順はフェーズ1計画 Task 10 と `docs/setup.md`(スモーク後に作成)を参照

---

## 3. フェーズ2で追加するテスト

| 対象 | 方法 |
|---|---|
| knowledge-digest | 候補の組・振り分け・案どうしの検査は core の決定論のユニットテスト。Jev は `urlopen` / `judge_pairs` を差し替え、鍵なし(unavailable)・呼び出し失敗(非ゼロ終了)・聞き直し1回・取得失敗で held を検証する。閾値は正解付きの評価セット(`scripts/eval/run_dedupe_eval.py`、Jev実呼び出し)で決める |
| ナリッジ品質 | 出典URL生存チェック(リンク切れ検出) |
| pricing計算機(着手する場合) | 取得日付きの代表見積りをゴールデンデータとして固定して突合する。**ライブ料金APIをテストに含めない**(クラウド非依存のため単一の公式Calculatorを正解に置けない) |

---

## 4. テストの書き方

- テストコードは **What** を表現する: テストを読めば「何が満たされるべきか(仕様)」が分かるように書く(表現の分担: workflow.md Section 4)
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
