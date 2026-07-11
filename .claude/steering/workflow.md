# ワークフロールール

Medo の開発ワークフロー。スペック駆動(superpowersフロー)+TDDで進める。

---

## 1. ドキュメントの二層整理

| 層 | 場所 | 内容 |
|---|---|---|
| **人間用** | `docs/` | 設計ドキュメント(PRFAQ含む)・実装計画・セットアップ手順。正本(canonical) |
| **Agent用** | `.claude/` | steering(常時参照する要約・規約)と specs(フェーズ単位のAgent向け要約+正本へのポインタ) |

- 正本は常に `docs/` 側。`.claude/` 側は要約とポインタに留め、二重管理のドリフトを防ぐ
- 設計が変わったら: `docs/superpowers/specs/` を更新 → `.claude/steering/` と `.claude/specs/` の要約を同期

## 2. 着手前チェック(全エージェント共通)

1. `.claude/steering/product.md`(設計原則・差別化軸)を確認
2. タスクに応じて `tech.md` / `structure.md` / `testing.md` / `git.md` を確認
3. 実行中のフェーズの spec と実装計画を確認: `.claude/specs/<phase>/` → 正本 `docs/superpowers/{specs,plans}/`
4. 実装計画のチェックボックス(`- [ ]`)で現在地を把握する

## 3. 実行主体の使い分け(Claude / Codex / agy)

Medo の開発では実行主体を役割で分担する。**Claudeが統制者(オーケストレーター)** であり、他は実行担当。

| 役割 | 担当 | 例 |
|---|---|---|
| 企画視点での設計的判断・コミット | **Claude** | 設計承認、要件との整合性判断、コミット・ブランチ操作、Skill/CLIの契約変更判断 |
| 単純な実装・テスト・レビュー | Codex または agy(antigravity) | 実装計画のTaskに沿ったコード実装、ユニットテストの追加、一次レビュー |
| 大きなコンテキストが必要な処理 | **agy(antigravity)優先** | 長いドキュメント/コード全体の読み込みが要る調査、大量生成(スキャフォールド・網羅的テスト生成)、マイグレーション |

- 判断の最終権限と結果検証は常にClaudeが持つ。Codex/agyの出力を無検証で正としない(実行後は `uv run pytest` / `uv run ruff check .` で自分で確認する)
- 振り分けの基準に迷ったら: 「サービスの企画・設計の意思決定を伴うか」→ Claude、「手順が決まっている実装/テスト/レビューか」→ Codex/agy、「大きなコンテキスト読み込みが支配的か」→ agy
- 詳細な委譲手順は `antigravity` プラグインの steering/skill を参照(本ファイルは役割分担の方針のみを定める)

### 相互レビュープロトコル(要約)

中間生成物(スペック・実装計画・実装diff)は最小単位で相互レビューする。
**正本: `docs/superpowers/specs/cross-review-design.md`**(詳細な手段・裁定ルールはそちらを参照)。

- 原則: **作ったモデル ≠ レビューするモデル**。Claude作の生成物(スペック・計画・diff)は Codex + agy の両方が、agy/Codex作のdiffは Claude がレビューする。Claudeが最終裁定者で、指摘も無検証で採用しない
- **上限2ラウンド**(指摘往復のみに適用)。早期終了は重大指摘ゼロ+コードは pytest/ruff パス。テスト・リントパスは裁定でも免除されない絶対条件
- **記録**: コミット本文に `review: <レビュアー(+区切り)> <n>R / 重大<n>件解消 / 未解決<n>` を1行残す。PRを経由する変更(git.mdセクション1)は同じ記録をPR本文にも転記する

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
- 実装計画のTask単位はGitHub Issueに対応させ、Issue→worktree→PR→dev/mainマージで進める(詳細: git.mdセクション1、正本: `docs/superpowers/specs/issue-driven-workflow-design.md`)

## 5. 設計判断で迷ったら

1. `product.md` の設計原則(発想は自由・事実は縛る/三分担/要件は確定しない/鮮度契約/推測で補完しない)に照らす
2. 差別化軸の「やらない」リストに該当しないか確認する
3. それでも決まらないものはユーザーに確認する(特に: スコープ拡大、外部公開、課金が発生する変更)

## 6. 変更時の同期トリガー

| 変更 | 同時に更新するもの |
|---|---|
| CLIのコマンド体系・出力形式 | `skills/src/*.md`(SkillはCLIとの契約で動く)+ Skill evalケース再実行 |
| ドメインスキーマ(要件・カタログ・生成物) | `structure.md` のストレージパス表、関連するSkill本文 |
| services.yaml(対象サービス) | ETLの手動実行でカタログ再構築 |
| 設計そのもの | `docs/superpowers/specs/` → steering/specs要約の同期(Section 1) |
| フェーズ完了 | `product.md` のフェーズ計画表、`.claude/specs/` に次フェーズを追加 |

## 7. 日常運用(フェーズ1)

```bash
# カタログ更新(手動・週次目安)
MEDO_BACKEND=local uv run medo etl run --since <前回実行日> --services vertex-ai,cloud-run

# Skill更新後の再配布
python skills/build.py && cp -r skills/dist/claude/* ~/.claude/skills/
```

フェーズ3でETLはCloud Scheduler+Cloud Run Jobに自動化し、Monitoringアラートを追加する(それまで監視ワークフローは持たない)。

## 8. 実案件での利用フロー(ドッグフーディング)

1. ホスト(Claude Code / agy)で `medo-hearing` → 要件保存(v1)
2. `medo-propose-architecture` → 根拠付きアーキ案を生成・保存
3. 案を見て要件の過不足に気づいたら要件を更新(v2) → `medo requirements diff` で陳腐化した生成物を確認 → 再生成
4. 使いにくさ・不足を感じたら、その場で直さずIssueメモとして `docs/feedback.md` に追記し、次の設計サイクルで扱う
