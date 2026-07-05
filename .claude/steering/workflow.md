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

## 3. 機能開発ワークフロー(スペック駆動)

```
アイデア/要望
  → superpowers:brainstorming(設計の対話・承認)
  → 設計ドキュメント作成: docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
  → superpowers:writing-plans(実装計画: docs/superpowers/plans/)
  → 実行: superpowers:subagent-driven-development または executing-plans
  → 検証(testing.md)→ コミット(git.md)
```

- 設計承認前に実装を始めない
- 実装計画のTask単位で「失敗テスト→実装→パス→コミット」を回す(計画にステップとコードが明記されている)
- 計画から外れる判断が必要になったら、勝手に進めず計画・specを更新してから実装する

## 4. 設計判断で迷ったら

1. `product.md` の設計原則(発想は自由・事実は縛る/三分担/要件は確定しない/鮮度契約/推測で補完しない)に照らす
2. 差別化軸の「やらない」リストに該当しないか確認する
3. それでも決まらないものはユーザーに確認する(特に: スコープ拡大、外部公開、課金が発生する変更)

## 5. 変更時の同期トリガー

| 変更 | 同時に更新するもの |
|---|---|
| CLIのコマンド体系・出力形式 | `skills/src/*.md`(SkillはCLIとの契約で動く)+ Skill evalケース再実行 |
| ドメインスキーマ(要件・カタログ・生成物) | `structure.md` のストレージパス表、関連するSkill本文 |
| services.yaml(対象サービス) | ETLの手動実行でカタログ再構築 |
| 設計そのもの | `docs/superpowers/specs/` → steering/specs要約の同期(Section 1) |
| フェーズ完了 | `product.md` のフェーズ計画表、`.claude/specs/` に次フェーズを追加 |

## 6. 日常運用(フェーズ1)

```bash
# カタログ更新(手動・週次目安)
MEDO_BACKEND=local uv run medo etl run --since <前回実行日> --services vertex-ai,cloud-run

# Skill更新後の再配布
python skills/build.py && cp -r skills/dist/claude/* ~/.claude/skills/
```

フェーズ3でETLはCloud Scheduler+Cloud Run Jobに自動化し、Monitoringアラートを追加する(それまで監視ワークフローは持たない)。

## 7. 実案件での利用フロー(ドッグフーディング)

1. ホスト(Claude Code / agy)で `medo-hearing` → 要件保存(v1)
2. `medo-propose-architecture` → 根拠付きアーキ案を生成・保存
3. 案を見て要件の過不足に気づいたら要件を更新(v2) → `medo requirements diff` で陳腐化した生成物を確認 → 再生成
4. 使いにくさ・不足を感じたら、その場で直さずIssueメモとして `docs/feedback.md` に追記し、次の設計サイクルで扱う
