# Medo(目処)

アイデアから「目処が立つ」までを最速にする、Google Cloud上流工程Agentケイパビリティ(Agent + Skill + CLI)。発想は自由に、事実は縛る。

## Steering(常時参照)

@.claude/steering/product.md
@.claude/steering/tech.md
@.claude/steering/structure.md

## タイミング別の参照先

| タイミング | 参照 |
|---|---|
| タスク着手前(ワークフロー・着手前チェック) | @.claude/steering/workflow.md |
| テストを書く・実行する・完了を主張する前 | @.claude/steering/testing.md |
| コミット・ブランチ操作の前 | @.claude/steering/git.md |

## Specs / Plans

- 現行フェーズのAgent用要約: `.claude/specs/phase1/spec.md`(タスク一覧: `.claude/specs/phase1/tasks.md`)
- 正本(人間用): 設計 `docs/superpowers/specs/medo-design.md` / 実装計画 `docs/superpowers/plans/medo-phase1.md`
- ドキュメントは二層整理: **docs/ = 人間用(正本)、.claude/ = Agent用(要約+ポインタ)**。設計変更は正本を先に更新し要約を同期する

## 絶対に守ること

1. 数値・launch_stage・鮮度の通り道にLLMを挟まない(事実はカタログ値・CLI出力のみ)
2. CLI・ツールが失敗したら推測で補完せず失敗を報告する
3. テストとリントが通ることを確認してからコミットする(`uv run pytest` / `uv run ruff check .`)
4. 設計承認前に実装を始めない(スペック駆動: workflow.md参照)
5. 実行主体はClaudeが統制する: **担当は workflow.md Section 3 の担当表(唯一の定義箇所)に従う**(担当表の更新で変更可能。最終判断・検証・コミットが常にClaudeであることは不変)。中間生成物は相互レビュー(作成モデル≠レビューモデル、上限2ラウンド)を通す

## よく使うコマンド

```bash
uv sync --all-packages   # 依存解決
uv run pytest            # 全テスト
uv run ruff check .      # リント
uv run medo --help       # CLI
python skills/build.py   # Skill配布物のビルド
```
