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

---

## 2. コミットの作者情報

- 作者名・メールアドレスはリポジトリにハードコードしない(公開リポジトリのため)。ローカルの `git config user.name` / `user.email` の設定値をそのまま使う
- 新しいリポジトリ/環境ではユーザー本人が `git config user.email <自分のメール>` を設定する
- AIエージェントがコミットする場合は Co-Authored-By トレーラーを付ける(ハーネスの規約に従う)

---

## 3. コミットメッセージ

### 形式(Conventional Commits・日本語)

```
<type>(<scope>): <subject>
```

| Type | 用途 |
|---|---|
| `feat` | 新機能 |
| `fix` | バグ修正 |
| `docs` | ドキュメントのみ |
| `refactor` | 機能変更を伴わない整理 |
| `test` | テストの追加・修正 |
| `chore` | ビルド設定・依存関係・ツール類 |

### Scope

`core` / `cli` / `etl` / `skills` / `webapp` / `steering` を使う。ドキュメント全般は scope なしの `docs:` でよい。

### 例

```
feat(core): 鮮度判定付きカタログストア
feat(etl): リリースノート取得とGemini構造化(検証必須・注入可能)
docs(steering): tech.md にLLM使い分け表を追加
```

### 規約

- 日本語・50文字以内・命令形推奨、1コミット1変更
- 実装計画実行時は計画のTask単位でコミット(計画にコミットメッセージが明記されている)
- デバッグコード・コメントアウトの残骸を含めない

---

## 4. コミットしてはいけないもの

- シークレット: `.env*`、`*.pem`、`service-account*.json`、APIキー
- ローカル設定: `.claude/settings.local.json`
- ビルド成果物: `.venv/`、`__pycache__/`、`skills/dist/`、`dist/`
- 個人・顧客の固有名詞を含むヒアリング実データ(要件ストアは MEDO_HOME 側にあり、リポジトリには入れない)

事故が起きた場合(コードレビューで発覚 / 既にGitHubにpush済みのいずれでも)は、削除コミットで済ませず**履歴ごと遡って完全に除去する**方針を取る:
1. `git filter-repo` 等でシークレット・PIIを含む全コミットの内容を書き換える(単純なamend/rebaseでは不十分な場合はこちらを使う)
2. `git reflog expire --expire=now --all && git gc --prune=now` でローカルの残骸を削除
3. `git log -p --all` で全文検査して残存ゼロを確認する
4. **既にリモート(GitHub)にpush済みの場合は、書き換え後の履歴を force push して置き換える**(このリポジトリで実施済みの手順)

---

## 5. コミット前の自己チェック

```
□ uv run pytest が通る(コード変更時)
□ git status で意図しないファイルが含まれていない(特に git add -A の巻き込み注意)
□ デバッグ用 print が残っていない
□ シークレット・顧客固有情報が含まれていない
□ コミットメッセージが規約に従っている
```

---

## 6. 緊急時

- 通常の取り消しは `git revert <hash>`(履歴保持)を第一選択
- main への force push は、履歴からの機密・PII除去(Section 4)以外では行わない。機密・PII除去が目的の場合はGitHub上への影響(既存clone・fork・共同作業者)を認識した上で force push する
