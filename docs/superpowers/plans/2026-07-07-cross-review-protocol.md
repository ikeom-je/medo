# 相互レビュープロトコル反映 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 承認済みスペック `docs/superpowers/specs/2026-07-07-cross-review-design.md` の相互レビュープロトコルを `.claude/steering/workflow.md` と `CLAUDE.md` に反映する。

**Architecture:** ドキュメントのみの変更。workflow.md Section 3(実行主体の使い分け)にプロトコル本文(マトリクス・ラウンド・終了条件・記録)を追記し、CLAUDE.md の「絶対に守ること」5項に相互レビューへの言及を同期する。コードは変更しない。

**Tech Stack:** Markdown(steering規約)

## Global Constraints

- ドキュメント二層整理: 正本は `docs/`、`.claude/` は要約+ポインタ(スペックの詳細を steering に丸写ししない)
- コミットメッセージは Conventional Commits・日本語(`docs(steering): ...`)
- コミット本文に `review:` 行を残す(本プロトコル自身の初適用)

---

### Task 1: workflow.md へのプロトコル追記と CLAUDE.md 同期

**Files:**
- Modify: `.claude/steering/workflow.md`(Section 3「実行主体の使い分け」)
- Modify: `CLAUDE.md`(「絶対に守ること」5項)

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-07-07-cross-review-design.md`(承認済みスペック)
- Produces: なし(終端タスク)

- [ ] **Step 1: workflow.md Section 3 にプロトコルを追記**

Section 3 の既存の3つの箇条書き(「判断の最終権限〜」「振り分けの基準〜」「詳細な委譲手順〜」)の後に、以下を追記する:

```markdown

### 相互レビュープロトコル

中間生成物(スペック・実装計画・実装diff)は最小単位で相互レビューする。
原則: **作ったモデル ≠ レビューするモデル**、Claudeが最終裁定者、指摘も無検証で採用しない。
(設計の正本: `docs/superpowers/specs/2026-07-07-cross-review-design.md`)

| 生成物 | 作成者 | レビュアー | 手段 |
|---|---|---|---|
| スペック | Claude | agy(Gemini) | antigravity:delegate で観点指定レビュー(設計原則整合・見落とし・曖昧さ) |
| 実装計画 | Claude | agy(Gemini) | 同上(Taskの抜け・依存関係・テスト戦略) |
| 実装Taskのdiff | agy / Codex | Claude | Claude自身がdiffレビュー+pytest/ruffを自分で実行 |
| Claudeが直接書いたコード | Claude | agy(Gemini) | antigravity:review(現diffのクロスモデルレビュー) |

- **上限2ラウンド**(レビュー→修正→再レビューで打ち止め)。上限到達時は未解決事項を列挙してClaudeが裁定
- **早期終了条件**(両方満たしたら終了): 重大指摘(欠陥・設計原則違反・要件不整合)ゼロ、かつコードは `uv run pytest` + `uv run ruff check .` パス
- 好みレベルの指摘はラウンドを消費せずClaude裁定で即確定
- 設計原則に関わる対立・スコープ拡大・課金が発生する変更はユーザーにエスカレーション
- **記録**: コミット本文に `review: <レビュアー> <n>R / 重大<n>件解消 / 未解決<n>` を1行残す。実装計画Taskの完了条件にレビュー完了を含める
```

- [ ] **Step 2: CLAUDE.md「絶対に守ること」5項を更新**

現在の5項:

```markdown
5. 実行主体はClaudeが統制する: 企画視点の設計判断・コミットはClaude、単純な実装/テスト/レビューはCodexかagy、大きなコンテキストが必要な処理はagy(antigravity)に振り分ける(詳細: workflow.md Section 3)
```

を以下に置換する:

```markdown
5. 実行主体はClaudeが統制する: 企画視点の設計判断・コミットはClaude、単純な実装/テスト/レビューはCodexかagy、大きなコンテキストが必要な処理はagy(antigravity)に振り分ける。中間生成物は相互レビュー(作成モデル≠レビューモデル、上限2ラウンド)を通す(詳細: workflow.md Section 3)
```

- [ ] **Step 3: 整合確認**

Run: `grep -n "相互レビュー" .claude/steering/workflow.md CLAUDE.md`
Expected: workflow.md のプロトコル見出しと CLAUDE.md 5項の両方がヒットする

Run: `grep -c "2ラウンド" .claude/steering/workflow.md`
Expected: 1以上

- [ ] **Step 4: レビュー(本プロトコルの初適用)**

Claudeが書いたドキュメント変更なので、agy に diff レビューを依頼する:

Run: `git diff` の内容を `antigravity:review` またはdelegateでレビュー(観点: スペックとの不整合・二層整理違反=詳細の丸写しになっていないか)
Expected: 重大指摘ゼロ(指摘があれば修正して再レビュー、上限2ラウンド)

- [ ] **Step 5: コミット**

```bash
git add .claude/steering/workflow.md CLAUDE.md
git commit -m "docs(steering): 相互レビュープロトコルをworkflow.mdに組み込み

review: agy <n>R / 重大<n>件解消 / 未解決<n>"
```
