# 開発ワークフローのマルチエージェント移植性 設計

## 背景・課題

現行の `workflow.md` Section 3(実行主体の使い分け)は「Claude Code + Codex + agy が揃っている」前提で担当表を定義しており、不変条件として「最終判断・検証・merge・コミットの統制は常にClaude(オーケストレーター)」と明記している。

しかし実際の利用環境は一定ではなく、Claude Codeが使えずCodex単体・agy単体で作業する状況が起こり得る。その場合でも同じ `git.md`/`workflow.md` の手順に従って、Issue→worktree→PR→マージのサイクルを一人称で回せる必要がある。

あわせて、Skill配布の実装調査で次が判明した: **Claude Code・Codex・agyの3ツールはいずれも同一のSkill形式(`<name>/SKILL.md`、YAML frontmatter + 本文)をネイティブサポートしている**。agyはプロジェクトルート直下の`.agents/skills/<name>/SKILL.md`を自動検出する(`~/.gemini/antigravity-cli/builtin/skills/agy-customizations/SKILL.md`のCustomization Discovery節で確認)。Codexは`~/.codex/skills/<name>/SKILL.md`(`config.toml`の`[features] skills = true`)。これまでの想定(「agyはfrontmatterなしの平文形式が必要」)は誤りで、**3ツールとも同一ビルド出力をそのまま配置場所にコピーするだけで動く**。この発見により、Skill配布は「ホストごとに異なる形式へ変換する」のではなく「単一形式を複数の配置先にコピーする」問題に単純化される。

本設計は、**現行の「全員揃っている場合の分担」は変更せず**、それに加えて「利用可能なエージェントの組み合わせが変わる環境」に対応するための拡張を定義する。エージェント専用pluginの模倣(例: Claude Codeの`Task`ツールをCodex/agyに再現する等)は行わない。

## スコープ

1. `workflow.md` Section 3への「エージェント可用性プロファイル」表の追加
2. `AGENTS.md` の記述をクラウド非依存の現行スコープに同期し、Skill参照先を統一形式に修正
3. `skills/build.py` を「ホスト別に異なる形式へ変換」から「単一形式を1箇所に出力」に簡素化
4. `tech.md` のSkill配布コマンド例を3ホスト分のコピー手順(うちagyはプロジェクトスコープ)に更新

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

### 2. Skill配布形式の統一(build.py・ディレクトリ構成)

`skills/src/` を現行の「1ファイル=1 Skill(`<name>.md`)」から「1フォルダ=1 Skill(`<name>/SKILL.md`)」に変更する。これが3ホスト共通のネイティブ形式そのものであるため、以後は変換ではなくコピーだけで配布できる。

- `skills/build.py`: frontmatter必須項目(`name`・`description`)の検証を行った上で、`skills/src/<name>/SKILL.md` を `skills/dist/<name>/SKILL.md` にコピーする単純な処理に簡素化する(ホスト別分岐・frontmatter除去ロジックを削除)
- `skills/tests/test_build.py`: 「`dist/<name>/SKILL.md`が生成され、frontmatterの`name`が一致する」ことを検証する形に書き換える(旧・claude/agy二形式テストは不要になる)

### 3. 配置先(deploy)

ビルド出力は3箇所にコピーする。Claude Code・Codexはホームディレクトリ配下(マシン単位、コピーが必要)、agyはプロジェクトルート直下(リポジトリ単位)。

```bash
python skills/build.py
cp -r skills/dist/* ~/.claude/skills/   # Claude Code(ユーザーレベル)
cp -r skills/dist/* ~/.codex/skills/    # Codex CLI(ユーザーレベル)
cp -r skills/dist/* .agents/skills/     # agy(プロジェクトレベル。リポジトリ直下から自動検出)
```

`.agents/skills/` は `skills/dist/` 同様ビルド成果物のため `.gitignore` に追加し、コミットしない(利用者が配布コマンドを実行して都度生成する運用を3ホストで統一する)。

### 4. AGENTS.mdの同期・修正

- 冒頭の説明文を CLAUDE.md と同じクラウド非依存の文言(「クラウド非依存の上流工程Agentケイパビリティ...実装手段としてGCPを選ぶ案件が多い想定」)に更新する
- 「Medo Skills」セクションを、ホスト別の形式差の説明ではなく「`python skills/build.py`後、上記3コマンドのいずれかで自ホストに配置する」という単一の案内に統一する

## テスト方針

- `skills/tests/test_build.py`: 新フォルダ構成(`skills/src/<name>/SKILL.md`)に対応した単一形式の生成テストに書き換える
- workflow.md/AGENTS.mdの変更はドキュメントのみのためユニットテスト対象外。`uv run pytest`全体が引き続きパスすることを確認する

## 影響範囲

- `skills/src/{hearing,propose-options,grow-prfaq}.md` を `skills/src/{medo-hearing,medo-propose-options,medo-grow-prfaq}/SKILL.md` にリネーム・移動する(既存本文の内容は変更不要)
- `.gitignore`: `.agents/skills/` を追加
- `docs/superpowers/plans/medo-phase1.md`: Task 9の完了条件(build.pyの出力形式)が変わるため、本設計の実装後に軽微な追記が必要
- `.claude/steering/structure.md` Section 4(`skills/`ディレクトリ構成の説明)を新フォルダ構成に同期
