# Medo(目処)

> ビジネスの打ち手に「目処」をつける上流工程Agent。
> 発想は自由に、事実は縛る。

業界・ビジネス状況・経営思想のヒアリングから始め、出典付きの市場・国策・業界動向データとフェルミ推定に裏づけられた打ち手候補(既存の解決/破壊的業務改革/新規市場開拓)をミニPRFAQとして比較提示し、What/Whyの合意を最速でつくる **クラウド非依存の上流工程Agentケイパビリティ(Agent + Skill + CLI)** です。合意した打ち手は、鮮度保証付き技術ナリッジに基づく技術的背景・効果を備えた完全版PRFAQに育てます。

## 何を解決するか

- What/Whyの合意がないまま **How(システム要件・アーキ検討)に突入** して起きる後戻り
- 市場・国策・業界動向を踏まえた打ち手比較が毎回手作業で、**提案の説得力が経験と勘に依存** する
- LLMの学習知識では追いつけない **AI/ML系サービスの更新速度**(「今なら解決できること」の見落とし)
- 提案が実行ごとに揺れて **比較検討・意思決定の土台にならない**
- 課題・要件整理の成果が案件ごとに **使い捨て** になる

## アプローチ: 役割の三分担

| 役割 | 担当 | 決定論性 |
|---|---|---|
| 手順(ヒアリング・打ち手提案・PRFAQ育成の進め方) | Skill(ホストLLMが実行) | 生成的 |
| 事実と計算(ファクト検証・フェルミ計算・技術ナレッジ・要件保存) | `medo` CLI + core | 決定論 |
| かさばる検索(市場・国策・業界動向・技術/サービス情報) | ホストLLMの検索+出典必須の保存 | 生成的だが出典必須 |

要件ドキュメント(背景・理念・課題・要件)はバージョン付きの「生きた成果物」で、生成物(ミニPRFAQ候補セット・完全版PRFAQ等)はその時点の要件バージョン・引用ファクト・引用ナレッジエントリに必ず紐づきます。要件や事実の鮮度が変わったら、陳腐化した生成物を機械的に検出して作り直せます。フェルミ推定の計算はLLMではなくコードが行います。

## 使い所: `medo` CLIは独立Agentではない

`medo` はSkill(手順書)の一部として、**ホストLLM(Claude Code / Codex / agy)がシェルから呼び出す決定論ツール**です。`gh` や `git` のように単体では会話も判断もしません。実行主体は常にホスト側のAgentで、`medo` はその手順の中で事実の保存・検証・計算だけを担います。

```
[ホスト] Claude Code(Claude) / Codex / agy(Gemini)   ← 会話・判断をするのはここだけ
    │ シェル実行
[Skill]  investigate → review → dialogue → decide   ← 標準周回の手順書(生成的)
         + propose-options / grow-prfaq
    │ 手順の中で呼ぶ
[CLI]    medo requirements / facts / fermi / knowledge / artifacts / status
         medo check / review / respond / checkpoint
```

自律的なmulti-agent構成は意図的に採らない設計方針(差別化軸を参照)。会話Agentは1体(ホストLLM)のみで、CLIは決定論的な道具箱として振る舞います。

## セットアップ: 各Agentツールに対応させる

Skillは3ホスト共通の `<name>/SKILL.md` 形式(YAML frontmatter + 本文)です。**ホスト別の変換は不要**で、ビルドして各ホストの配置先へコピーするだけです。

```bash
uv sync --all-packages       # 依存解決(medo CLI が使えるようになる)
python skills/build.py       # skills/src/ を検証して skills/dist/ へ出力
```

| ホスト | 配置先 | スコープ | 備考 |
|---|---|---|---|
| Claude Code | `~/.claude/skills/` | ユーザーレベル | コピーが必要 |
| Codex CLI | `~/.codex/skills/` | ユーザーレベル | コピーが必要 |
| agy(Antigravity) | `<リポジトリ直下>/.agents/skills/` | プロジェクトレベル | リポジトリ直下から自動検出 |

```bash
mkdir -p ~/.claude/skills ~/.codex/skills .agents/skills
cp -r skills/dist/* ~/.claude/skills/
cp -r skills/dist/* ~/.codex/skills/
cp -r skills/dist/* .agents/skills/
```

`medo` CLI にPATHが通っていれば、どのホストからでも同じ手順が動きます(`uv run medo` でも可)。**Skill本文を変更したら `python skills/build.py` からやり直して再配布します**。

`skills/dist/` と `.agents/skills/` はビルド成果物で `.gitignore` 対象です。`git worktree` で新しい作業ディレクトリを作った直後は存在しないため、その都度ビルドし直してください。

### どのホストで何を実行してもよい

案件の状態(要件・ファクト・生成物・進行記録)はすべて `MEDO_HOME`(既定 `~/.medo`)のストアにあり、ホストのコンテキストには何も残りません。そのため**ステージごとに違うホストで実行できます** — 調査はagy、現状整理はClaude、内部レビューはCodex、といった使い分けが成立し、途中でモデルが変わっても `medo status` を読めば再開できます。

誰が実行したかは生成物の `--generated-by claude|codex|gemini` とレビューの `--reviewed-by`(+ `human`)に記録されます。

## 標準周回(4ステージ)

暗黙知は現状(AsIs)と理想(ToBe)を何度も往復して初めて出てきます。往復は頭の中では回らず、**各ステージで成果物を出し、レビューし、顧客にぶつけて反応を得る**ことで進みます。

| Skill | ステージ | やること |
|---|---|---|
| `medo-investigate` | 調べる・仕立てる | 公開情報と生の声を集め、現状を整理して報告書と討議用スライドまで作る |
| `medo-review` | 内部検証 | 顧客に見せる前に論理矛盾・GAP・表現上の懸念を洗い出す |
| `medo-dialogue` | ぶつける・反応を得る | 提示して確認・共感・異議を記録する |
| `medo-decide` | 振り返る・次へ進む | 反応を要件に反映し、往復継続か次段階かを判断する |

**固定の状態機械ではありません**。どのステージから始めても成立し、CLIは順序を強制せず現在地(`medo status` の `actions`)だけを返します。合意後は `medo-propose-options` → `medo-grow-prfaq` で打ち手の比較と完全版PRFAQへ進みます。

**回ること自体が価値**です。チェックリストが埋まらなくても周回を重ねること自体が解像度を上げるため、周回ごとに「今回新たに分かったこと」(`round_delta`)を返します。「顧客があるべき姿を語れないと分かった」ことも成果として数えます。

## ステータス

**フェーズ2の決定論層(優先度1〜4)・Skill(優先度5)・最終提案スライドとフェーズ完了ゲート(優先度6)まで完了。** フェーズ1のWhat/Why縦切りに加えて、標準周回を回すためのドメインモデル(現状・あるべき姿・GAP・真因・課題・仮説)・進行記録・4階層診断・Skill 4本を実装し、まっさらな環境からの通し確認を完了しています。

| フェーズ | 内容 | 状態 |
|---|---|---|
| 1 | core(要件・ファクト・フェルミ・技術ナレッジ)+ `medo` CLI + Skill(hearing / propose-options / grow-prfaq) | 完了 |
| 2(優先度1〜4) | ドメインモデル・ID規約・変更manifest・生成物の依存グラフ・進行記録・収束判定・4階層診断 | 完了 |
| 2(優先度5) | 標準周回のSkill 4本 + 討議用スライド生成 | 完了 |
| 2(優先度6) | 最終提案スライド + `phase_signoff` ゲート | 完了 |
| 2(後続) | knowledge-digest・decision-roadmap・build-mock・propose-architecture・pricing・簡易Webアプリ | 詳細設計が未了 |
| 3 | 運用自動化: 類似案件検索 /(必要になれば)特定クラウドAPI連携ETLをプラグインとして追加 | 未着手 |
| バックログ | AWS比較・MCPアダプタ・A2A(Gemini Enterprise)・チーム展開 | — |

## ドキュメント

| 対象 | 場所 |
|---|---|
| フェーズ1の設計(PRFAQ含む) | [docs/superpowers/specs/medo-design.md](docs/superpowers/specs/medo-design.md) |
| フェーズ2の設計(索引) | [docs/superpowers/specs/medo-phase2-design.md](docs/superpowers/specs/medo-phase2-design.md) |
| 実装計画 | [medo-phase1.md](docs/superpowers/plans/medo-phase1.md) / [medo-phase2-core.md](docs/superpowers/plans/medo-phase2-core.md) / [medo-phase2-skills.md](docs/superpowers/plans/medo-phase2-skills.md) / [medo-phase2-final.md](docs/superpowers/plans/medo-phase2-final.md) |
| セットアップと通し確認の記録 | [docs/setup.md](docs/setup.md) |
| 使い方 | [docs/usage.md](docs/usage.md) |
| Agent向けエントリポイント | [CLAUDE.md](CLAUDE.md)(Claude Code) / [AGENTS.md](AGENTS.md)(agy等) |
| Agent向け規約(steering) | `.claude/steering/` |

## 開発

```bash
uv sync --all-packages       # 依存解決
uv run pytest                # テスト
uv run ruff check .          # リント
uv run medo --help           # CLI
python skills/build.py       # Skill配布物のビルド(Claude Code/Codex/agy共通形式)
```

Skillの再現性は `MEDO_TRACE` で測れます。同じ初期状態から各ホストに1周させ、CLI呼び出し列のJSONLをdiffすると、Skillが飛ばした操作が見えます。**自由文・ファイルパス・案件IDは伏字になる**ため、トレースはそのまま共有できます(何が残り何が伏せられるかは [docs/usage.md](docs/usage.md#skillの再現性を測る) を参照)。

```bash
MEDO_TRACE=/tmp/claude.jsonl uv run medo status --project <id>
```

技術スタック: Python 3.12+ / uv workspace / pydantic / typer / Firestore(本番ストレージに選ぶ場合のみ、任意)

## ライセンス

[MIT License](LICENSE)
