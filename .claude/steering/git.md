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
