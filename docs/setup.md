# セットアップ手順(手動スモーク結果)

実環境で実際に使ったコマンド・環境変数・ハマりどころの記録。medoは自分専用・チーム展開前提のツールであり、本手順はまず自分のマシンで動かすためのもの。第1〜4節はフェーズ1 Task 10(Issue #37)、第5節はフェーズ2 Task 21(Issue #65)の結果。

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

---

## 5. フェーズ2決定論層の手動スモーク(Task 21)

実案件 `medo-ops`(フェーズ1のドッグフーディングで作った要件v2・生成物7件・ファクト3件)に対して、フェーズ2の標準周回を1周させた記録。**自動テストでは検出できない、実データでの通し動作**を見るのが目的。

```bash
export MEDO_BACKEND=local     # 既定。クラウド認証は不要
```

### 5.1 フェーズ1データの移行(ID採番)

フェーズ2はノードにIDを持たせる。既存データは `requirements get` → そのまま `requirements save` するだけで採番される。

```bash
uv run medo requirements get --project medo-ops --format json > /tmp/req.json
uv run medo requirements save --project medo-ops --file /tmp/req.json   # saved: v3
```

**内容の追加とID採番は分けて保存する**。同じ保存でやると manifest の `id_only_migration` が立たず、「採番だけの保存では生成物を陳腐化させない」性質が働かない。

結果: 課題5件に `ch-1`〜`ch-5`、未確定事項2件に `oq-1`/`oq-2` が採番され、採番簿 `meta/id_watermark.json` は `{"ch": 5, "oq": 2}` になった。manifest v3 は `id_only_migration: true`。

### 5.2 標準周回を1周

まず `/tmp/req.json` に内部AsIs・ToBe・決裁者を1件ずつ追記する。**既存ノードのIDは書き換えない**(書き換えると過去のイベント・生成物の参照が別のノードを指す)。

```python
import json
d = json.load(open("/tmp/req.json"))
d["as_is"].append({
    "text": "打ち手候補の比較検討は毎回手作業で、過去案件の資料を探すところから始まる",
    "confidence": "assumed", "visibility": "internal", "scope": "core",
})
d["to_be"].append({
    "text": "過去案件のナレッジを跨いで参照し、比較検討の初稿がその場で出る",
    "confidence": "assumed", "scope": "core",
})
d["stakeholders"].append({
    "text": "medoの利用者本人(提案者)", "role": "提案者",
    "confidence": "confirmed", "is_decision_maker": True,
})
json.dump(d, open("/tmp/req.json", "w"), ensure_ascii=False, indent=2)
```

```bash
uv run medo requirements save --project medo-ops --file /tmp/req.json     # saved: v4

# 出力(生成物の本文ファイルを先に用意する)
printf '# medo-ops 現状調査・分析報告書\n\n打ち手候補の比較検討が毎回手作業である現状を整理した。\n' > /tmp/as-is-report.md
printf '# medo-ops 討議用スライド\n\n- 現状\n- 論点\n' > /tmp/slides.md

uv run medo artifacts save --project medo-ops --type as-is-report \
  --requirements-version 4 --generated-by claude --file /tmp/as-is-report.md
uv run medo artifacts save --project medo-ops --type slides --slide-kind discussion \
  --derived-from as-is-report-v1 --requirements-version 4 \
  --generated-by claude --file /tmp/slides.md

# レビュー → ぶつける → 振り返る
uv run medo check add --project medo-ops --check reality_gap --result completed
uv run medo review add --project medo-ops --report as-is-report-v1 \
  --slides slides-v1 --outcome approved --reviewed-by human
uv run medo respond add --project medo-ops --stakeholder sh-1 \
  --artifact as-is-report-v1 --purpose as_is_alignment --reaction empathized
uv run medo checkpoint answer --project medo-ops --responds-to ev-1 --answer generate

uv run medo status --project medo-ops --view full
```

### 5.3 確認項目と結果

| # | 確認したこと | 結果 |
|---|---|---|
| 1 | フェーズ1の既存データ(課題5件・未確定事項2件)が読め、初回保存でID採番される | ✅ `ch-1`〜`ch-5` / `oq-1`〜`oq-2` |
| 2 | その保存の manifest に `id_only_migration: true` が立ち、生成物が stale にならない | ⚠️ **初回は失敗**(下記)。Issue #89 修正後に再実行して合格 |
| 3 | `internal` な AsIs を追加した保存で `MilestoneDetected` が記録される | ✅ `ev-1`(`condition: internal_as_is_first_added`) |
| 4 | `medo status` の `actions` 先頭が `answer_tobe_checkpoint` になる | ✅ `refs: ["ev-1"]` / `reason: 節目で未回答` |
| 5 | `next_step` がフェーズ1の値域のまま返る | ✅ 移行直後は `up-to-date`、依存セクションを変えた保存後は `regenerate-stale-artifacts` |
| 6 | 討議用スライドを保存すると `expression_safety` が `run_check` に現れる(対象が無い間は出ない) | ✅ 保存前は9件、保存後に `expression_safety` が加わり10件 |
| 7 | `review add` が `--slides` の親子関係を検証する | ✅ 別レポート由来のスライド・存在しないIDのいずれも exit 1 + `error:` |
| 8 | 1周させた後の `round_delta` が非空になり、`progress_count` が0でない | ✅ `new_internal_as_is: 1` / `progress_count: 1` |

### 5.4 スモークで見つかった不具合(いずれも修正済み)

**確認項目2の失敗 → [Issue #89](https://github.com/ikeom-je/medo/issues/89) / PR #91**

ID採番だけの保存の直後に、`medo status` が生成物3件すべてを `stale: true`、`next_step: regenerate-stale-artifacts` として返した。`ArtifactStore.freshness()` は正しく `fermi-v3: current` / `mini-prfaq-v2, prfaq-v2: outdated` を返しており、**statusの後方互換フィールドだけがフェーズ1の文書全体ルール(`requirements_version < 最新版 → stale`)のまま**だった。同じJSONの中で `actions` は `freshness()` を使うため、`next_step` が再生成を促すのに `actions` に `regenerate_stale_artifacts` が無い、という矛盾も起きていた。

**自動テストで検出できなかった理由**: 既存テストが「要件を更新したら生成物が stale になる」というフェーズ1の挙動を仕様として固定しており、フェーズ2で意図的に変えた部分を守る側に回っていた。実データで `fermi`(要件のどのセクションにも依存しない型)が誤って stale 判定されて初めて表面化した。

修正後に同じ移行を再実行し、`id_only_migration: true` / 生成物3件すべて `stale: false` / `next_step: up-to-date` を確認した。

**移行前データでの偽の進捗 → 同 Issue #89 で修正**

ID未採番の要件どうしを突き合わせると空文字IDが同一ノードとみなされ、移行前の `medo status` が `confidence_raised: ["", "", "", ""]` / `progress_count: 4` を返していた。実体のない進捗報告であり、空文字IDを突き合わせ対象から外した。

**トレースの伏字漏れ → [Issue #90](https://github.com/ikeom-je/medo/issues/90) / PR #92**

Task 21のドキュメント同期レビュー中に検出。`MEDO_TRACE` は自由文とファイルパスを `<redacted>` にする設計だが、値ではなく**キー側**に自由文が残る経路が2つあった。typer が受理する結合形式 `--statement=<自由文>`、および値そのものが `--` で始まる場合(`--statement "-- 顧客要望"`)である。トークンが整形式のオプション名かどうかで判定するよう直した。

### 5.5 ハマりどころ

- `git worktree` で作った作業ディレクトリでは `uv sync --all-packages` を実行しないと `medo` コマンドが解決しない(`error: Failed to spawn: medo`)
- スモークは実データ(`~/.medo`)を書き換える。先に `cp -r ~/.medo <backup>` を取っておくと、修正後の再検証を移行前の状態からやり直せる。実際に Issue #89 の修正確認はこのバックアップを `MEDO_HOME` に指定して再実行した
- 上のコマンド列の `as-is-report-v1` / `slides-v1` / `ev-1` は、**その案件に生成物とイベントが1件も無い状態から始めた場合のID**。既に周回した案件で再実行するときは `medo artifacts list` / `medo status --view workflow` で実際のIDを確認するか、バックアップから復元してやり直す
