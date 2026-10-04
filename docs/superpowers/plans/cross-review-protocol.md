# 相互レビュープロトコル反映 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 承認済みスペック `docs/superpowers/specs/cross-review-design.md` の相互レビュープロトコルを `.claude/steering/workflow.md` と `CLAUDE.md` に反映する。

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
- Consumes: `docs/superpowers/specs/cross-review-design.md`(承認済みスペック)
- Produces: なし(終端タスク)

- [x] **Step 1: workflow.md Section 3 にプロトコルを追記**

Section 3 の既存の3つの箇条書き(「判断の最終権限〜」「振り分けの基準〜」「詳細な委譲手順〜」)の後に、以下を追記する:

```markdown

### 相互レビュープロトコル(要約)

中間生成物(スペック・実装計画・実装diff)は最小単位で相互レビューする。
**正本: `docs/superpowers/specs/cross-review-design.md`**(詳細な手段・裁定ルールはそちらを参照)。

- 原則: **作ったモデル ≠ レビューするモデル**。Claude作の生成物(スペック・計画・diff)は Codex + agy の両方が、agy/Codex作のdiffは Claude がレビューする。Claudeが最終裁定者で、指摘も無検証で採用しない
- **上限2ラウンド**(指摘往復のみに適用)。早期終了は重大指摘ゼロ+コードは pytest/ruff パス。テスト・リントパスは裁定でも免除されない絶対条件
- **記録**: コミット本文に `review: <レビュアー(+区切り)> <n>R / 重大<n>件解消 / 未解決<n>` を1行残す
```

(注: 当初案はマトリクス・終了条件の詳細を workflow.md に転記する内容だったが、レビュー(codex+agy)で二層整理違反の指摘を受け、要約+正本ポインタに圧縮した)

- [x] **Step 2: CLAUDE.md「絶対に守ること」5項を更新**

現在の5項:

```markdown
5. 実行主体はClaudeが統制する: 企画視点の設計判断・コミットはClaude、単純な実装/テスト/レビューはCodexかagy、大きなコンテキストが必要な処理はagy(antigravity)に振り分ける(詳細: workflow.md Section 3)
```

を以下に置換する:

```markdown
5. 実行主体はClaudeが統制する: 企画視点の設計判断・コミットはClaude、単純な実装/テスト/レビューはCodexかagy、大きなコンテキストが必要な処理はagy(antigravity)に振り分ける。中間生成物は相互レビュー(作成モデル≠レビューモデル、上限2ラウンド)を通す(詳細: workflow.md Section 3)
```

- [x] **Step 3: 整合確認**

Run: `grep -n "相互レビュー" .claude/steering/workflow.md CLAUDE.md`
Expected: workflow.md のプロトコル見出しと CLAUDE.md 5項の両方がヒットする

Run: `grep -c "2ラウンド" .claude/steering/workflow.md`
Expected: 1以上

- [x] **Step 4: レビュー(本プロトコルの初適用)**

Claudeが書いたドキュメント変更なので、Codex と agy の両方に diff レビューを依頼する:

Run: `git diff` の内容を Codex MCP と `antigravity:review`(観点を細かく指定する場合はdelegate可)の両方でレビュー(観点: スペックとの不整合・二層整理違反=詳細の丸写しになっていないか)
Expected: 両者とも重大指摘ゼロ(指摘があれば修正して再レビュー、上限2ラウンド)

- [x] **Step 5: コミット**

```bash
git add .claude/steering/workflow.md CLAUDE.md
git commit -m "docs(steering): 相互レビュープロトコルをworkflow.mdに組み込み

review: codex+agy <n>R / 重大<n>件解消 / 未解決<n>"
```
