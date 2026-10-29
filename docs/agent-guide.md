# Agent向けガイド(ホスト共通)

Medo を Claude Code / Codex / agy(Antigravity)のどれから触るときも、**このファイルが唯一の入口**。

ホスト別のエントリポイント([CLAUDE.md](../CLAUDE.md) / [AGENTS.md](../AGENTS.md))は各ホストが自動で読む場所であり、本ファイルを指すだけで内容を持たない。**規約を足すときは本ファイルだけを直す** — 両方に書き写すと、片方を更新したときにもう片方がずれる。

---

## 0. どのAgentが使えるかは環境で変わる

利用できるAgentは、組織のルール・契約・プロジェクトの制約で変わる。**本ガイドは特定のAgentが揃っていることを前提にしない**。

セッション開始時に、自分がどの可用性プロファイル(全員揃う / Codex単体 / agy単体 / Claude単体)に該当するかを、他ツールの有無から判断する。プロファイルによって「誰が計画・実装・レビューを担うか」が変わる。**判定基準と各プロファイルの担い方は [workflow.md](../.claude/steering/workflow.md) Section 3 が唯一の定義箇所**。判断に迷う場合はユーザーに確認する。

プロファイルが変わっても、**人間レビューが必要かどうかの判定基準は変わらない**([git.md](../.claude/steering/git.md) Section 1 step 7)。

---

## 1. 常時参照(steering)

| ファイル | 内容 |
|---|---|
| [product.md](../.claude/steering/product.md) | プロダクト思想・設計原則・差別化軸 |
| [tech.md](../.claude/steering/tech.md) | 技術スタック・LLM使い分け・コマンド |
| [structure.md](../.claude/steering/structure.md) | ディレクトリ構造・命名規則・依存方向 |

## 2. タイミング別の参照先

| タイミング | 参照 |
|---|---|
| タスク着手前(ワークフロー・着手前チェック・担当分担) | [workflow.md](../.claude/steering/workflow.md) |
| テストを書く・実行する・完了を主張する前 | [testing.md](../.claude/steering/testing.md) |
| コミット・ブランチ操作の前 | [git.md](../.claude/steering/git.md) |

**`.claude/` というディレクトリ名だが、中身はホスト非依存の規約である**。Claude Code 以外のホストもこのパスを読む。

## 3. 現在地(Specs / Plans)

| 層 | 場所 |
|---|---|
| Agent用要約(現行フェーズ) | [.claude/specs/phase2/spec.md](../.claude/specs/phase2/spec.md)(タスク一覧: [tasks.md](../.claude/specs/phase2/tasks.md))。フェーズ1は `.claude/specs/phase1/` |
| 正本の設計(人間用) | [medo-phase2-design.md](superpowers/specs/medo-phase2-design.md)(索引)。フェーズ1は `medo-design.md` |
| 正本の実装計画(人間用) | [medo-phase2-core.md](superpowers/plans/medo-phase2-core.md) / [medo-phase2-skills.md](superpowers/plans/medo-phase2-skills.md) / [medo-phase2-final.md](superpowers/plans/medo-phase2-final.md) |

ドキュメントは二層。**docs/ = 人間用(正本)、.claude/ = Agent用(要約+ポインタ)**。設計変更は正本を先に更新し、要約を同期する。

## 4. Medo Skill を使う

Skillの一覧・各ホストへの配置手順は [README](../README.md#セットアップ-各agentツールに対応させる)、使い方は [docs/usage.md](usage.md) を参照。

```bash
python skills/build.py       # skills/src/ を検証して skills/dist/ へ出力
```

配置先はホストで異なる(Claude Code と Codex はユーザーレベルへコピー、agy はリポジトリ直下の `.agents/skills/` を自動検出)。

---

## 5. 絶対に守ること

1. **数値・鮮度・技術ナレッジの通り道にLLMを挟まない**(事実は facts / knowledge・CLI出力のみ)
2. **CLI・ツールが失敗したら推測で補完せず失敗を報告する**
3. **テストとリントが通ることを確認してからコミットする**(`uv run pytest` / `uv run ruff check .`)
4. **設計承認前に実装を始めない**(スペック駆動: workflow.md Section 4)
5. **実行主体は workflow.md Section 3 の担当表・可用性プロファイルに従う**(唯一の定義箇所)。中間生成物は相互レビュー(作成モデル ≠ レビューモデル、上限2ラウンド。単体プロファイルでは自己レビューに緩和)を通す
6. **表現の分担を守る**: コードには How、テストコードには What、コミットログには Why、コードコメントには Why not(詳細: workflow.md Section 4)

---

## 6. よく使うコマンド

```bash
uv sync --all-packages   # 依存解決
uv run pytest            # 全テスト
uv run ruff check .      # リント
uv run medo --help       # CLI
python skills/build.py   # Skill配布物のビルド
```
