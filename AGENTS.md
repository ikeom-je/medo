# Medo(目処) — Agent向けガイド

アイデアから「目処が立つ」までを最速にする、クラウド非依存の上流工程Agentケイパビリティ(Agent + Skill + CLI)。発想は自由に、事実は縛る。

このファイルは agy(Antigravity/Gemini)・codex 等、Claude Code 以外のAgentツール向けのエントリポイント。内容は CLAUDE.md と同一の参照体系を持つ。

## Steering(常時参照)

- プロダクト思想・設計原則・差別化軸: @.claude/steering/product.md
- 技術スタック・LLM使い分け・コマンド: @.claude/steering/tech.md
- ディレクトリ構造・命名規則・依存方向: @.claude/steering/structure.md

## タイミング別の参照先

| タイミング | 参照 |
|---|---|
| タスク着手前(ワークフロー・着手前チェック) | @.claude/steering/workflow.md |
| テストを書く・実行する・完了を主張する前 | @.claude/steering/testing.md |
| コミット・ブランチ操作の前 | @.claude/steering/git.md |

## Specs / Plans

- 現行フェーズのAgent用要約: `.claude/specs/phase1/spec.md`(タスク一覧: `.claude/specs/phase1/tasks.md`)
- 正本(人間用): 設計 `docs/superpowers/specs/medo-design.md` / 実装計画 `docs/superpowers/plans/medo-phase1.md`

## Medo Skills(フェーズ1 Task 9 のビルド後に有効)

`python skills/build.py` を実行後、自ホストの配置先にコピーすると利用可能になる(`tech.md` セクション6のコマンド例参照)。agyはプロジェクトルート直下の `.agents/skills/` を自動検出するため、`mkdir -p .agents/skills && cp -r skills/dist/* .agents/skills/` を実行すればよい。

- 課題・方針の構造化: `medo-hearing` Skillの手順に従う
- 打ち手候補の提案: `medo-propose-options` Skillの手順に従う
- PRFAQ育成: `medo-grow-prfaq` Skillの手順に従う

## 絶対に守ること

1. 数値・鮮度・技術ナレッジの通り道にLLMを挟まない(事実はfacts/knowledge・CLI出力のみ)
2. CLI・ツールが失敗したら推測で補完せず失敗を報告する
3. テストとリントが通ることを確認してからコミットする(`uv run pytest` / `uv run ruff check .`)
4. 設計承認前に実装を始めない(スペック駆動: workflow.md参照)
5. 実行主体は workflow.md Section 3 の担当表・エージェント可用性プロファイル(唯一の定義箇所)に従う(担当表の更新で変更可能。「全員揃う」プロファイルでは最終判断・検証・コミットは常にClaude、単体プロファイルではそのプロファイルのオーケストレータが担う)。中間生成物は相互レビュー(作成モデル≠レビューモデル、上限2ラウンド。単体プロファイルでは自己レビューに緩和)を通す
6. 表現の分担を守る: **コードには How、テストコードには What、コミットログには Why、コードコメントには Why not** を書く(詳細: workflow.md Section 4)
