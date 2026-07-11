# GitHub Issue駆動の開発プロセス 設計

- ステータス: 承認済み
- スコープ: Medoの開発ワークフロー(実装計画Task → Issue → worktree実装 → PR → dev/mainマージ)

---

## 1. 背景・目的

これまでの運用は「実装計画のTaskをworktreeでfeatureブランチに実装 → ローカルでdevへ直接マージ」であり、GitHub Issue・PRを一切経由していなかった。この状態には次の課題があった:

- 作業の追跡可能性がGitHub上に残らない(進捗・意図・レビュー記録がリポジトリのコミットログにしか残らない)
- 相互レビュー(Codex/agy)の結果がPR上で可視化されず、後から検証しにくい
- dev/mainの品質ゲートが「Claudeの自己申告」に閉じており、外部から見た安定性の担保が弱い

本設計が満たすべき指針(ユーザー確認済み):
- **安定性**: 重要な変更(契約変更・課金関連・レビュー未解決)は人間承認を経由する
- **多角的視点**: Codex + agyによる相互レビューをPR上に記録し、単一モデルの見落としを防ぐ
- **トークンコスト効率**: 軽微な変更まで人間レビューを待たず、Claudeが検証済みの範囲は自動マージしてループを止めない
- **スピード**: Issue→worktree→PR→自動マージの機械的な流れで、Task単位の待ち時間を最小化
- **ビジネスと開発のフィードバックループ**: Issueに実装計画Taskの意図を記録し、GitHub上でMedoというプロダクトの進捗が人間にも追える状態にする(Medo自身が「上流工程の意思決定を高速化する」プロダクトであることと一貫させる)

## 2. 全体フロー

```
実装計画のTask N(docs/superpowers/plans/medo-phase1.md)
  → gh issue create(ラベル phase1、本文にTask概要+計画へのリンク)
  → git worktree add .worktrees/task-N -b feature/<issue番号>-<説明>
  → TDD実装(Codex/agyに委譲、Claudeがpytest/ruffで検証)
  → Claude作のdiffは相互レビュー(Codex+agy、上限2ラウンド。workflow.md既存プロトコル)
  → git push -u github feature/<issue番号>-<説明>
  → gh pr create --base dev(本文に "Closes #<issue番号>" + テスト結果 + レビュー記録)
  → 重要度判定(下記3.)
      - 通常 → Claudeが gh pr merge --squash で自動マージ → Issueは自動close
      - 重要 → Claudeが人間レビューを依頼(gh pr edit --add-reviewer 等)→ 承認後にマージ
  → git worktree remove .worktrees/task-N
  → (Task 10=統合スモーク完了、フェーズ1完了時)
      → gh pr create --base main → マージはユーザーが実行
```

## 3. dev向けPRの重要度判定(人間レビューを要する条件)

以下いずれかに該当する場合、Claudeは自動マージせず人間レビューを依頼する:

1. **スキーマ/契約変更**: CLIコマンド体系・Storageパス設計など、`structure.md`のストレージパス表やSkill契約に影響する変更
2. **GCP認証・課金が絡む変更**: ETL(BigQuery/Billing/Gemini API等)の実クライアント呼び出しを初めて追加する変更
3. **相互レビュー未解決**: Codex/agyの相互レビューが上限2ラウンドに達しても重大指摘が解消しない場合

上記に該当しない場合(通常のTask実装・ドキュメント更新・テスト追加等)は、Claudeがテスト結果と相互レビュー結果を確認した上で自動マージする。

main向けPRは重要度によらず常に人間承認を経由する(フェーズ全体の完了節目のため)。

## 4. Issue/PRのテンプレート

**Issue本文**:
```markdown
## 概要
(実装計画のTask見出しと概要を転記)

## 参照
- 実装計画: docs/superpowers/plans/medo-phase1.md の Task N
- 依存: #<依存Issue番号>(あれば)
```
ラベル: `phase1`(以降のフェーズも `phase2` 等で対応)

**ブランチ名**: `feature/<issue番号>-<短い説明>`(例: `feature/3-requirements-doc`)

**PR本文**:
```markdown
## 変更内容
(概要)

## テスト結果
- uv run pytest: <件数> passed
- uv run ruff check .: <結果>

## レビュー記録
review: <レビュアー(+区切り)> <n>R / 重大<n>件解消 / 未解決<n>

Closes #<issue番号>
```

## 5. 既存Task 1・Task 2の扱い

- **Task 1**: Issue・PRを経由せず既にdevへマージ済み。遡及の実行はしない(過去のマージ操作をやり直さない)。追跡可能性の記録目的でGitHub Issue #1を作成し、該当コミットハッシュを本文に記載した上で作成時点でcloseする
- **Task 2**: 実装・コミットはworktree(`feature/task2-storage`)上で完了しているが、devへのマージは未実行。Issue #2を作成後、既存コミットのままこのブランチをリモートにpushし、Issue #2に紐づくPRとして本設計のフローに乗せてdevへマージする(実装のやり直しはしない)

## 6. steering反映箇所

| ファイル | 変更 |
|---|---|
| `.claude/steering/git.md` | セクション1(ブランチ戦略)を書き換え。「リモートなし」前提を削除し、Issue→ブランチ→PR→dev/mainの運用を明記。マージ実行者(Claude/ユーザー)の区分を追加 |
| `.claude/steering/workflow.md` | Section 4(機能開発ワークフロー)にTaskごとのIssue化ステップを追記。相互レビュープロトコル(既存)とdev向けPRの重要度判定を接続 |
