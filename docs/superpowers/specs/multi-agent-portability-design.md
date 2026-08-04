# 開発ワークフローのマルチエージェント移植性 設計

## 背景・課題

現行の `workflow.md` Section 3(実行主体の使い分け)は「Claude Code + Codex + agy が揃っている」前提で担当表を定義しており、不変条件として「最終判断・検証・merge・コミットの統制は常にClaude(オーケストレーター)」と明記している。

しかし実際の利用環境は一定ではなく、Claude Codeが使えずCodex単体・agy単体で作業する状況が起こり得る。その場合でも同じ `git.md`/`workflow.md` の手順に従って、Issue→worktree→PR→マージのサイクルを一人称で回せる必要がある。あわせて、Skill配布物(`skills/dist/`)がCodexのネイティブ形式と噛み合っていない技術的な不整合も見つかった。

本設計は、**現行の「全員揃っている場合の分担」は変更せず**、それに加えて「利用可能なエージェントの組み合わせが変わる環境」に対応するための拡張を定義する。エージェント専用pluginの模倣(例: Claude Codeの`Task`ツールをCodex/agyに再現する等)は行わない。

## スコープ

1. `workflow.md` Section 3への「エージェント可用性プロファイル」表の追加
2. `AGENTS.md` の記述をクラウド非依存の現行スコープに同期し、Codex向けSkill参照先を修正
3. `skills/build.py` にCodexネイティブ形式(`dist/codex/<name>/SKILL.md`)の出力を追加
4. `tech.md` のSkill配布コマンド例にCodex向けコピー手順を追加

対象外(やらない): git.md/workflow.md自体を新規Skillとしてパッケージ化すること、実行時に読み込む機械可読な設定ファイル(例: `.claude/agents.yaml`)の新設、Claude Code以外のホストへの`Task`的なサブエージェント機構の移植。

## 設計

### 1. エージェント可用性プロファイル(workflow.md Section 3に追加)

既存の担当表(「全員揃う」場合の行別分担)はそのまま正本として維持する。その直後に、利用可能なエージェントの組み合わせ別プロファイルを追加する:

| プロファイル | オーケストレータ | 実装・テスト | レビュー | 備考 |
|---|---|---|---|---|
| 全員揃う(既定) | Claude | Codex(+agyは調査/資料) | Claude作→Codex+agy / Codex,agy作→Claude(相互レビュー) | 既存の担当表(本Section上部)通り |
| Codex単体 | Codex | Codex | Codex自己レビュー | git.md Section1の手順をCodexが単独で実行する |
| agy単体 | agy | agy | agy自己レビュー | 同上 |
| Claude単体 | Claude | Claude | Claude自己レビュー | 同上 |

**単体プロファイルでの相互レビュー原則の扱い**: 「作ったモデル≠レビューするモデル」は物理的に満たせないため、単体環境では自己レビューに緩和する。コミット本文の `review:` 行は `review: self 1R`(または相当)の形式で、単体実行であった旨を記録する。

**変わらないもの**: git.md Section1 step7の重要度判定(スキーマ/契約変更・GCP課金変更・重大指摘未解決の場合は人間レビューを依頼する基準)は、どのプロファイルでも同一に適用する。プロファイルが変わるのは「誰が計画・実装・レビューを担うか」であり、「人間レビューが必要かどうかの判定基準」ではない。

**プロファイルの決定方法**: 各セッション開始時、当該ツール(Claude Code / Codex CLI / agy)は自分がどのプロファイルに該当するかを、利用可能な他ツールの有無(MCP接続・CLI呼び出し可否)から自己判断する。判断に迷う場合はユーザーに確認する。

### 2. AGENTS.mdの同期・修正

- 冒頭の説明文を CLAUDE.md と同じクラウド非依存の文言(「クラウド非依存の上流工程Agentケイパビリティ...実装手段としてGCPを選ぶ案件が多い想定」)に更新する
- 「Medo Skills」セクションの参照先を分離する:
  - agy向け: 引き続き `skills/dist/agy/*.md`(frontmatter除去済みの平文。ホスト側にネイティブなSkillフォルダ機構がないため、手順書として直接読ませる)
  - codex向け: `skills/dist/codex/*/SKILL.md`(後述。Claude Codeと同一のfrontmatter付きフォルダ形式)を新たに案内する

### 3. skills/build.pyへのCodex向け出力追加

CodexのネイティブSkill機構(`~/.codex/skills/<name>/SKILL.md`、`config.toml`の`[features] skills = true`)は、Claude Codeの`dist/claude/<name>/SKILL.md`と同一のフォルダ+frontmatter形式である。そのため `build()` 関数に、`dist/claude/`と同一内容を`dist/codex/`にも書き出す処理を追加する(実質的にコピー。将来Codex固有の差分が必要になった場合のための独立出力とする)。

`skills/tests/test_build.py`に、`dist/codex/<name>/SKILL.md`の存在と内容(`dist/claude/`と同一)を検証するケースを追加する。

### 4. tech.mdのコマンド例更新

```bash
python skills/build.py
cp -r skills/dist/claude/* ~/.claude/skills/     # Claude Code
cp -r skills/dist/codex/* ~/.codex/skills/       # Codex CLI
# agy: skills/dist/agy/*.md をAGENTS.mdから参照
```

## テスト方針

- `skills/tests/test_build.py`: `dist/codex/<name>/SKILL.md`が生成され、`dist/claude/<name>/SKILL.md`と同一内容であることを確認するテストケースを追加(既存の`test_build_generates_claude_and_agy_dist`を拡張または新規テスト関数を追加)
- workflow.md/AGENTS.mdの変更はドキュメントのみのためユニットテスト対象外。`uv run pytest`全体が引き続きパスすることを確認する

## 影響範囲

- `docs/superpowers/plans/medo-phase1.md`: Task 9の完了条件に「Codex向けdist出力」が含まれていなかったため、本設計の実装後に軽微な追記が必要
- 既存の3 Skill本文(`skills/src/*.md`)自体の変更は不要(ビルド出力の追加のみ)
