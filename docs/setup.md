# セットアップ手順(フェーズ1統合スモーク結果)

Task10(統合スモーク、Issue #37)で実際に使ったコマンド・環境変数・ハマりどころの記録。medoは自分専用・チーム展開前提のツールであり、本手順はまず自分のマシンで動かすためのもの。

## 1. クラウド非依存構成の前提

medo CLI・coreの実行に必須のクラウド依存はない。既定バックエンド(`MEDO_BACKEND=local`、未設定時も同じ)はローカルJSON+markdownで完結し、外部API呼び出しは発生しない。

```bash
uv sync --all-packages
MEDO_BACKEND=local uv run medo --help
```

Firestoreを本番ストレージに選ぶ場合のみ`gcloud auth application-default login`等の認証が必要になる(フェーズ1のスモークでは未使用)。`MEDO_HOME`未設定時は`~/.medo`が既定のデータルート(要件・ファクト・生成物・knowledge/すべてここに保存される)。

## 2. ナレッジ洗練(フェーズ2)

フェーズ1では技術ナレッジ(`knowledge/{kind}/`)・案件固有ナレッジ(`knowledge/projects/{id}/`)ともに**追記のみ**で、重複統合・要約はしない。統合スモーク中も、同じ論文(arXiv:2311.17311)由来のfactをClaude/Gemini双方が独立に保存する場面があり、重複検知の仕組みがまだない点を実際に確認した。フェーズ2の`knowledge-digest`が解消する想定の課題。

## 3. Skill配置(Claude Code/Codex/agy)

3ホスト共通のSKILL.md形式(`skills/src/<name>/SKILL.md`)をビルドし、各ホストの配置先へコピーする。

```bash
python skills/build.py
mkdir -p ~/.claude/skills ~/.codex/skills .agents/skills
cp -r skills/dist/* ~/.claude/skills/   # Claude Code(ユーザーレベル)
cp -r skills/dist/* ~/.codex/skills/    # Codex CLI(ユーザーレベル)
cp -r skills/dist/* .agents/skills/     # agy(プロジェクトレベル。リポジトリ直下から自動検出)
```

**ハマりどころ**: `.agents/skills/`は`.gitignore`対象のビルド成果物置き場のため、`git worktree add`で新規worktreeを作った直後は存在しない。worktree側で作業する場合は毎回`python skills/build.py`から実行し直す必要がある(過去のworktreeにあった配置はコピーされない)。

## 4. What/Why縦切りの流れ

`medo-hearing` → `medo-propose-options` → `medo-grow-prfaq` の一連の流れを、Medo自身の運用課題(project: `medo-ops`)をドッグフーディング対象としてClaude Code・agy(Gemini)双方で実施した。

### 実行環境

- Claude Code: このリポジトリ内のSkill本文(`skills/src/*/SKILL.md`)を直接読み、手順に従ってCLIをシェル実行
- agy: `agy-job start -m gemini-3.7-flash-high --yolo --sandbox --dir .`でバックグラウンド委譲。同じ`skills/src/*/SKILL.md`を読ませ、同一要件(v2)に対して`--generated-by gemini`で生成物を保存させた

### 確認できたこと

1. `medo requirements save`→`saved: v1`、2回目以降は`saved: v2`と自動バージョン採番される
2. `medo facts save`は出典URL必須(market/policy/trend)のバリデーションを通り、`medo facts list`で出典・鮮度付き表示される
3. `medo fermi calc`はコードによる決定論計算(ast制限の四則演算+累乗)で、`--from-artifact <id>`により保存済みモデルから再計算できる(`fermi-v1`→`fermi-v2`で同じ結果を再現、要件更新後は新バージョンとして保存)
4. `medo artifacts save --type mini-prfaq`/`--type prfaq`は`--generated-by claude|gemini`の記録により、同一要件・同一ファクト根拠に対するClaude/Geminiの生成物比較が`medo artifacts list`で並べて確認できる
5. 要件をv2に更新すると、`medo status`が旧バージョンに依存する全生成物を`stale: true`として検出し、`next_step: regenerate-stale-artifacts`を返す。`medo requirements diff`も陳腐化した生成物IDを一覧表示する
6. 各Skill終了時の`medo knowledge save --project <id>`(案件固有ナレッジの追記)は正常動作し、対話の要点がmarkdownファイルとして`knowledge/projects/{id}/`に蓄積される

### 見つかった不具合(手順書側のバグ、修正済み)

- `docs/superpowers/plans/medo-phase1.md` Task10 Step1に`medo knowledge search --limit 20`という実在しないフラグの記載があった(実CLIは`--project`/`--kind`/`--format`のみ)。実行して初めて判明し、計画側を修正した

### agy実行時の追加の留意点

- agyのサンドボックス環境では既定の`PATH`に`~/.local/bin`が含まれておらず、`uv: command not found`が発生することがある。`export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"`で解決
- Gemini実行分の生成物(ファクトの転記等)は、Claude実行分と同様に出典との突合を人間またはClaude側でも検証すべき。実際に、Geminiが保存したファクトの数値自体は正確だったが「どのモデルでの実験結果か」という条件が転記時に欠落していたケースがあり、出典PDFを直接確認して修正した。転記精度がホストLLM依存であることの実例であり、`medo-design.md`が明記するトレードオフ(フェーズ2でCLIによる出典照合検証を追加予定)を裏づけた
