# GitHub Issue駆動の開発プロセス Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 承認済み設計 `docs/superpowers/specs/issue-driven-workflow-design.md` を反映し、以後の実装計画TaskをGitHub Issue→worktree→PR→dev/mainマージのフローに乗せる。あわせて既存のTask 1・Task 2を新フローに整合させる。

**Architecture:** コード変更はない。(1) `.claude/steering/git.md`・`workflow.md` にプロセスを明文化 (2) GitHub CLI(`gh`)でTask 1の遡及Issueを作成しclose (3) Task 2(実装済み・`feature/task2-storage`ブランチ)をIssue化しPR経由でdevへマージする。

**Tech Stack:** Markdown(steering)、GitHub CLI(`gh`)

## Global Constraints

- リポジトリ: カレントディレクトリのGitHubリモート(リモート名 `github`。`gh`はリポジトリ内で実行すれば`--repo`指定なしで自動解決される)
- コミットメッセージ末尾に `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` を付ける
- ドキュメントのみの変更・PR操作はdevブランチで直接進めてよい(git.md方針: 単一コミットの小変更はworktree不要)
- 設計ドキュメントの正本: `docs/superpowers/specs/issue-driven-workflow-design.md`(以下「正本」)

---

### Task 1: steering反映(git.md / workflow.md)

**Files:**
- Modify: `.claude/steering/git.md`(セクション1「ブランチ戦略」を書き換え)
- Modify: `.claude/steering/workflow.md`(Section 4「機能開発ワークフロー」にIssue化ステップを追記)

**Interfaces:**
- Consumes: 正本のSection 2(全体フロー)・Section 3(重要度判定)・Section 4(テンプレート)
- Produces: なし(以降のTaskはこの記述内容を運用として使う)

- [ ] **Step 1: git.md セクション1を書き換える**

現在の `.claude/steering/git.md` 冒頭〜セクション1(1〜20行目付近)は以下の内容になっている:

```markdown
# Git ルール

このリポジトリでの Git 運用ルール。個人開発・ローカルリポジトリ(現時点でリモートなし)を前提とし、チーム展開(バックログ)時に PR フローへ拡張する。

---

## 1. ブランチ戦略

現フェーズはトランクベース(main 中心)のシンプル運用。デプロイ環境の分離(dev/staging等)は行わない。

| ブランチ | 用途 |
|---|---|
| `main` | 唯一の長命ブランチ。テストが通る状態を保つ |
| `feature/<説明>` | 複数コミットにまたがる機能実装(実装計画のTask実行時など) |
| `fix/<説明>` | バグ修正 |

- ドキュメントのみの変更・単一コミットの小変更は main 直接コミット可
- 実装タスク(コード変更)は **必ず git worktree 上の feature/fix ブランチで作業する**(`git worktree add .worktrees/<name> -b <branch>`。`.worktrees/` は .gitignore 対象)。同一リポジトリを複数マシン・複数セッションで並行開発するため、作業ディレクトリの競合を防ぐ目的
- 完了したら worktree 上で `uv run pytest` 等の検証を通してから main へマージし、`git worktree remove .worktrees/<name>` で片付ける
- GitHub リモート追加後は main への直接 push を止め、PR 経由に移行する
```

これを次の内容に置換する(冒頭の説明文とセクション1全体):

```markdown
# Git ルール

このリポジトリでの Git 運用ルール。GitHub Issue駆動で進める(正本設計: `docs/superpowers/specs/issue-driven-workflow-design.md`)。

---

## 1. ブランチ戦略

`main`(公開安定版)/ `dev`(開発統合)の2ブランチ運用。実装計画のTask 1件はGitHub Issue 1件に対応する。

| ブランチ | 用途 |
|---|---|
| `main` | 公開安定版。フェーズ完了(統合スモーク後)にdevからPRでマージ。マージは常にユーザー承認 |
| `dev` | 開発統合ブランチ。Task単位のPRがここにマージされる |
| `feature/<issue番号>-<説明>` | Issue 1件=Task 1件に対応する実装ブランチ |
| `fix/<issue番号>-<説明>` | バグ修正 |

**Issue→PR→マージの流れ:**

1. 実装計画のTaskごとに `gh issue create`(ラベル `phase1`、本文に実装計画へのリンク)
2. `git worktree add .worktrees/<name> -b feature/<issue番号>-<説明> dev` で作業ディレクトリを分離
3. TDDで実装(Codexに委譲、必要な調査はagy。Claudeが `uv run pytest` / `uv run ruff check .` で検証)する
4. **相互レビューを実施**(workflow.mdの相互レビュープロトコル。Claude作のdiffはCodex+agy、agy/Codex作のdiffはClaude。上限2ラウンド)し、結果を `review:` 行に記録してworktree上でコミット
5. `git push -u github feature/<issue番号>-<説明>`
6. `gh pr create --base dev`(本文に "Closes #<issue番号>" + テスト結果 + レビュー記録を転記)
7. **重要度判定**(次のいずれかに該当する場合のみ人間レビューを依頼、それ以外はClaudeが自動マージ):
   - スキーマ/契約変更(CLIコマンド体系・Storageパス等、Skill契約に影響)
   - GCP認証・課金が絡む変更(ETLの実クライアント呼び出しの初回追加)
   - 相互レビューが上限2ラウンドでも重大指摘未解決
   - 該当する場合: `gh pr edit --add-reviewer <ユーザー>` 等で人間レビューを依頼し、承認後にマージ
   - 該当しない場合: Claudeが `gh pr merge --squash` で自動マージ(Issueは自動close)
8. `git worktree remove .worktrees/<name>` で片付ける
9. フェーズ完了(統合スモークTask完了)時: `gh pr create --base main --head dev` をClaudeが作成し、**マージは常にユーザーが実行**

- 実装計画のTaskに紐づく変更は必ずIssue→PRを経由する。**この例外はTaskに紐づかない、ごく小さな臨時のドキュメント修正(typo・リンク切れ修正等)にのみ適用**され、その場合はworktreeを使わずdevへ直接コミットしてよい(mainへの直接コミットはしない)
- 詳細なテンプレート(Issue本文・PR本文の具体形式)は正本設計のSection 4を参照
```

- [ ] **Step 2: workflow.md Section 4にIssue化ステップを追記する**

`.claude/steering/workflow.md` の現在の Section 4 は次の内容:

```markdown
## 4. 機能開発ワークフロー(スペック駆動)

```
アイデア/要望
  → superpowers:brainstorming(設計の対話・承認)
  → 設計ドキュメント作成: docs/superpowers/specs/<topic>-design.md
  → superpowers:writing-plans(実装計画: docs/superpowers/plans/<topic>.md)
  → 実行: superpowers:subagent-driven-development または executing-plans
  → 検証(testing.md)→ コミット(git.md)
```

- ファイル名に日付プレフィックスは付けない(git履歴が作成日・変更履歴を持つため冗長)。本文内にも日付ヘッダーは書かない

- 設計承認前に実装を始めない
- 実装計画のTask単位で「失敗テスト→実装→パス→コミット」を回す(計画にステップとコードが明記されている)
- 計画から外れる判断が必要になったら、勝手に進めず計画・specを更新してから実装する
```

「- 計画から外れる判断が必要になったら、勝手に進めず計画・specを更新してから実装する」の直後に以下を追記する:

```markdown
- 実装計画のTask単位はGitHub Issueに対応させ、Issue→worktree→PR→dev/mainマージで進める(詳細: git.mdセクション1、正本: `docs/superpowers/specs/issue-driven-workflow-design.md`)
```

- [ ] **Step 3: 整合確認**

Run: `grep -n "Issue" .claude/steering/git.md .claude/steering/workflow.md`
Expected: git.md に複数のIssue関連記述、workflow.md に追記した1行がヒットする

- [ ] **Step 4: レビュー**

Claude作のドキュメントdiffなので、正本設計の重要度判定に従い、契約変更ではないため相互レビュー(Codex+agy)のみ実施すればよい(人間レビュー不要)。`git diff` をCodex MCPと `antigravity:review` の両方でレビューし、両者の重大指摘ゼロを確認する。指摘があれば修正し上限2ラウンドで再レビュー。

- [ ] **Step 5: コミット**

```bash
git add .claude/steering/git.md .claude/steering/workflow.md
git commit -m "docs(steering): GitHub Issue駆動プロセスをgit.md/workflow.mdに反映

review: <レビュアー> <n>R / 重大<n>件解消 / 未解決<n>"
```

---

### Task 2: Task 1の遡及Issue作成

**Files:**
- なし(GitHub Issue作成のみ、リポジトリ内ファイル変更なし)

**Interfaces:**
- Consumes: Task 1のマージコミット `3d02116`(`Merge feature/task1-uv-workspace into dev`)
- Produces: GitHub Issue #1(作成後即close)

- [ ] **Step 1: Issue #1を作成してcloseする**

Run:
```bash
gh issue create \
  --title "Task 1: uv workspace モノレポ土台(core/cli/etl)" \
  --label phase1 \
  --body "$(cat <<'EOF'
## 概要
uv workspaceによるモノレポ土台(core/cli/etl の3パッケージ)を作成する。

## 参照
- 実装計画: docs/superpowers/plans/medo-phase1.md の Task 1

## 備考
本Issueは遡及作成。実装・マージは本Issue作成前にIssue/PRを経由せず完了済み。
マージコミット: 3d02116(Merge feature/task1-uv-workspace into dev)
EOF
)"
```
Expected: Issue番号(例: `#1`)が標準出力に表示される

- [ ] **Step 2: 作成したIssueをcloseする**

Run: `gh issue close <Issue番号> --comment "遡及記録のため作成時点でclose(実装済み・マージ済み)"`
Expected: `Closed issue #<N>`

---

### Task 3: Task 2をIssue化しPRでdevへマージ

**Files:**
- なし(`feature/task2-storage`ブランチの内容は変更しない。マージのみ)

**Interfaces:**
- Consumes: `feature/task2-storage`ブランチ(コミット `ec9b97d`、`core/src/medo_core/storage.py` 等。Task 1完了時点の`dev`から分岐)
- Produces: `dev`ブランチへのマージ、GitHub Issue #2(マージ後自動close)

**注意:** `feature/task2-storage` は `9aea99b`(Task1完了時点)から分岐しており、その後 `dev` は `fed018f`(ファイル名リネーム)・`27e8d46`(Issue駆動設計)まで進んでいる。コンフリクトの有無を確認してからPRを作成する。

- [ ] **Step 1: Issue #2を作成する**

Run:
```bash
gh issue create \
  --title "Task 2: Storage(Protocol + ローカルJSON + Firestore)" \
  --label phase1 \
  --body "$(cat <<'EOF'
## 概要
Storage Protocol、LocalJsonStorage、FirestoreStorage、get_storage()を実装する。

## 参照
- 実装計画: docs/superpowers/plans/medo-phase1.md の Task 2

## 備考
実装は本Issue作成前にfeature/task2-storageブランチ上で完了済み
(コミット ec9b97d、pytest 5件パス確認済み)。本Issueはこの後PR経由でマージする。
EOF
)"
```
Expected: Issue番号(例: `#2`)が表示される

- [ ] **Step 2: feature/task2-storageにdevの最新を取り込む**

```bash
cd /home/pi/develop/medo/.worktrees/task2-storage
git fetch github dev
git merge github/dev
```
Expected: コンフリクトなくマージ完了、またはコンフリクトが出た場合は内容を確認して解消する(今回のdev側の変更はdocsのリネーム+新規specファイルのみで、Task2の変更ファイル`core/src/medo_core/storage.py`等とは重複しないため、コンフリクトは想定されない)

- [ ] **Step 3: マージ後にテストとリントを再確認する**

Run: `cd /home/pi/develop/medo/.worktrees/task2-storage && UV_CACHE_DIR=/tmp/uv-cache uv run pytest -v && UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .`
Expected: 全テストPASS(Task1のsmoke 1件+Task2のstorage 5件=6件)、ruffは `All checks passed!`

- [ ] **Step 4: ブランチをpushしPRを作成する**

```bash
cd /home/pi/develop/medo/.worktrees/task2-storage
git push -u github feature/task2-storage
gh pr create --base dev --head feature/task2-storage \
  --title "feat(core): Storage抽象とLocalJSON/Firestoreバックエンド" \
  --body "$(cat <<'EOF'
## 変更内容
Storage Protocol、LocalJsonStorage(テスト・ローカル運用用)、FirestoreStorage(本番用薄いラッパー)、get_storage()(env MEDO_BACKEND切替)を実装。

## テスト結果
- uv run pytest: 6 passed(Task1 smoke 1件 + Task2 storage 5件)
- uv run ruff check .: All checks passed!

## レビュー記録
review: codex 2R / 重大0件 / 未解決0(Codexへの実装委譲、Claudeがテスト実行で検証)

Closes #2
EOF
)"
```
Expected: PR番号とURLが表示される

- [ ] **Step 5: 重要度判定と自動マージ**

Task 2はスキーマ/契約変更ではなく(Storage抽象は内部実装で、CLIコマンド体系・Skill契約に未接続)、GCP実クライアント呼び出しの追加でもなく(FirestoreStorageはMagicMockでテストのみ)、相互レビューも重大指摘なしのため、正本設計Section 3の重要度判定により**自動マージ対象**。

Run: `gh pr merge --squash --delete-branch=false <PR番号>`
Expected: マージ完了、Issue #2が自動close

- [ ] **Step 6: ローカルの後片付け**

```bash
cd /home/pi/develop/medo
git checkout dev
git pull github dev
git worktree remove .worktrees/task2-storage
git branch -d feature/task2-storage
```
Expected: `dev`に最新が反映され、worktree・ローカルブランチが削除される

- [ ] **Step 7: tasks.md・実装計画のチェックボックスを更新してコミット**

`.claude/specs/phase1/tasks.md` の該当行を更新:

```diff
-| 2 | Storage(Protocol + LocalJSON + Firestore) | 1 | 未着手 |
+| 2 | Storage(Protocol + LocalJSON + Firestore) | 1 | 完了 |
```

`docs/superpowers/plans/medo-phase1.md` のTask 2セクション(Step 1〜5の `- [ ] **Step` を `- [x] **Step` に変更)。

```bash
git add .claude/specs/phase1/tasks.md docs/superpowers/plans/medo-phase1.md
git commit -m "docs: Task2完了を進捗表・計画チェックボックスに反映"
git push github dev
```
