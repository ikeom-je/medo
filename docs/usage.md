# Medo 使い方ガイド

Medoは「ビジネスの打ち手に目処をつける」上流工程を支援する。**判断を代行せず、現在地と次にできることを返す**。

配置と各Agentツールへの対応は [README](../README.md#セットアップ-各agentツールに対応させる) を参照。

---

## 全体像

現状と理想を往復して合意をつくり、合意した打ち手を提案に育てる。

```
    ┌──────── 標準周回(現状と理想の合意をつくる)────────┐
    │                                                      │
    │  medo-investigate  調べる・仕立てる                  │
    │        ↓            現状を整理し、報告書とスライドを出す │
    │  medo-review       内部検証                          │
    │        ↓            顧客に見せる前に論点を研ぐ         │
    │  medo-dialogue     ぶつける・反応を得る               │
    │        ↓            確認・共感・異議を記録する          │
    │  medo-decide       振り返る・次へ進む                 │
    │        └───── 収束するまで1へ戻る ─────┘             │
    └──────────────────────┬───────────────────────────────┘
                           ↓ readiness が ready
    medo-propose-options   打ち手候補のミニPRFAQ比較
                           ↓ 合意
    medo-grow-prfaq        完全版PRFAQ(How+効果+ロードマップ)
```

**固定の順序ではない**。どのステージから始めてもよく、CLIは順序を強制しない。何をすべきかは常に `medo status` が返す。

**回ること自体が価値である**。チェックリストが埋まらなくても、周回を重ねること自体が解像度を上げる。「顧客があるべき姿を語れないと分かった」ことも成果として数える。

---

## 今どこにいるかを知る

```bash
medo status --project <id>                  # 既定は summary(actions が先頭)
```

`actions` が「次にできること」を優先順に返す。**Skillはこれを読んで動く**。

| view | 返すもの | 見たいとき |
|---|---|---|
| `summary`(既定) | `actions` + フェーズ1互換フィールド | ふだんはこれだけでよい |
| `actions` | 次にできることだけ | 手短に確認したい |
| `model` | 構造・リンク・カバレッジ | 何が繋がっていないか見たい |
| `workflow` | check・レビュー・反応・周回 | 進行状況を見たい |
| `readiness` | 収束判定と失敗している条件 | なぜ次へ進めないか知りたい |
| `full` | 4階層すべて | 全部見たい |

```bash
medo status --project <id> --view workflow
medo status --project <id> --include-scope secondary   # 診断範囲を広げる
```

### 主な `actions`

| code | 意味 |
|---|---|
| `answer_tobe_checkpoint` | 節目が未回答(最優先) |
| `resolve_objection` | 未解消の異議がある |
| `address_review_findings` | レビュー所見が未解決 |
| `draft_strawman_to_be` | 内部実態はあるが理想像がまだ無い |
| `generate_as_is_report` | 最新要件からの現状報告書が無い |
| `generate_discussion_slides` | 報告書に対応する討議用スライドが無い |
| `run_check` | 未確認のチェック項目がある |
| `explore_undeterminable` | 判断できなかった項目が残っている |
| `consider_promotion` | 未昇格の対立がある(課題にするか判断する) |
| `elicit_internal_as_is` | 現場の実態がまだ無い |
| `ground_confirmed_to_be` | 裏づけの無い確定ToBeがある |
| `request_to_be_go_ahead` | 決裁者の合意だけが未取得 |
| `regenerate_stale_artifacts` | 陳腐化した生成物がある |
| `proceed_to_propose_options` | 収束条件を満たした |
| `continue_hearing` | 上記のいずれにも該当しない |

### `next_step`(フェーズ1互換)

フェーズ1のSkillが値で分岐しているため、値域は変えていない。

| next_step | 意味 |
|---|---|
| `hearing` | 要件が未作成 |
| `propose-options` | 要件はあるが打ち手候補がない |
| `grow-prfaq` | 候補セットはあるが完全版PRFAQがない |
| `regenerate-stale-artifacts` | 生成物が陳腐化している |
| `up-to-date` | 生成物が最新に追従している |

---

## ステージとコマンドの対応

| ステージ | Skill | 主なCLI |
|---|---|---|
| 調べる・仕立てる | `medo-investigate` | `requirements template` / `requirements save` / `facts save` / `artifacts outline` / `artifacts save` |
| 内部検証 | `medo-review` | `check list` / `check add` / `review add` |
| ぶつける・反応を得る | `medo-dialogue` | `respond add` / `check add` |
| 振り返る・次へ進む | `medo-decide` | `requirements save` / `checkpoint answer` / `requirements diff` |
| 打ち手の提案 | `medo-propose-options` | `facts save` / `fermi calc` / `knowledge search` / `artifacts save --type mini-prfaq` |
| PRFAQ育成 | `medo-grow-prfaq` | `artifacts get` / `knowledge search` / `artifacts save --type prfaq` |

`medo-hearing` は `medo-investigate` に統合済み(移行期間中のポインタとして残している)。

---

## 案件を始める

`<id>` は自分で決める英数字slug(例 `yoyaku-system`)。事前登録は要らず、最初の保存で作られる。

```bash
medo status --project <id>                       # next_step: hearing が返る
medo requirements template > /tmp/req.yaml       # 雛形を取得
```

雛形はノードの例が**すべてコメントアウトされている**。埋める項目だけコメントを外す。**空のノードを保存するとIDが採番され、空の `to_be` が1件あるだけで診断段階が `convergence` に変わる**ため、埋まらない項目は書かない。

```bash
medo requirements save --project <id> --file /tmp/req.yaml
```

2回目以降は自動的に新しいバージョンになる。**既存ノードの `id` は書き換えない** — 書き換えると過去のイベント・生成物の参照が別のノードを指す。既存案件を更新するときは `medo requirements get --project <id> --format json` の出力を編集する。

誤字・言い回しの修正だけのセクションは `--editorial <section>` を宣言する。宣言が無ければ本文の変更は「要再生成」として扱われる(安全側)。

### IDはどこから得るか

`requirements save` は `saved: v1` としか返さない。後続のコマンドに渡すIDは次で確認する。

| ID | 例 | どこで得るか |
|---|---|---|
| ノード | `as-1` / `sh-1` / `hyp-1` | `medo requirements get --project <id> --format json`(保存時にcoreが採番) |
| 生成物 | `as-is-report-v1` / `slides-v1` | `medo artifacts list --project <id>` |
| イベント | `ev-1` | `medo status --project <id> --view workflow` の `loop.checkpoint.pending_ids`、または `actions` の `refs` |

---

## 生成物

```bash
medo artifacts outline --type slides --slide-kind discussion   # 章構成と表現の規約
medo artifacts save --project <id> --type as-is-report \
  --requirements-version <n> --generated-by claude --file /tmp/report.md
medo artifacts save --project <id> --type slides --slide-kind discussion \
  --derived-from as-is-report-v1 --requirements-version <n> \
  --generated-by claude --file /tmp/slides.md
medo artifacts list --project <id>
```

生成物は**セクション単位**で陳腐化を判定する。2段階あり、`stale`(要再生成)と `outdated`(差分確認推奨)を区別する。依存は `--derived-from` で辿り、親の陳腐化は子へ連鎖する。

`--generated-by claude|codex|gemini` を記録するため、同じ状態に対してモデルを変えて実行し、結果を比較できる。

---

## 進行を記録する

進行記録は要件とは別のイベントとして持つ。要件は保存のたびに版が進むため、反応やレビューを要件内に置くと記録した瞬間に旧版宛てになる。

```bash
# チェック項目の確認結果。artifact束縛の項目は --artifact が必須
medo check list                                  # どの項目がどの束縛か
medo check list --confirmer customer             # 顧客に確認する項目(スライドの章6に投影)
medo check add --project <id> --check reality_gap --result completed
medo check add --project <id> --check as_is_articulation --result completed \
  --artifact as-is-report-v1

# レビュー結果(報告書と討議用スライドをセットで)
medo review add --project <id> --report as-is-report-v1 --slides slides-v1 \
  --outcome approved --reviewed-by human
medo review add --project <id> --report as-is-report-v1 --slides slides-v1 \
  --outcome changes_requested --refs oq-1 --slide-finding "章3の表現を見直す"

# 顧客の反応。purpose によって対象が変わる
medo respond add --project <id> --stakeholder sh-1 --artifact as-is-report-v1 \
  --purpose as_is_alignment --reaction empathized
medo respond add --project <id> --stakeholder sh-1 \
  --purpose to_be_go_ahead --reaction agreed     # 要件宛て。--artifact を付けない

# 節目への回答。この周回で検証する仮説を1つ選ぶ
medo checkpoint answer --project <id> --responds-to ev-1 --answer generate --focus hyp-1
```

**判断できなかったことを失敗として扱わない**。`--result undeterminable` で記録し、扱いを `--disposition open|deferred|promoted` で示す。判断できなかったこと自体が次の周回の論点になる。

---

## 事実と計算

```bash
medo facts save --project <id> --kind market --statement "<出典に忠実な一文>" \
  --source <URL> --value 1234 --unit 億円 --retrieved 2026-09-01
medo facts list --project <id>
medo fermi calc --project <id> --file /tmp/model.yaml
medo knowledge search "<キーワード>"
```

**数値は出典に忠実に転記し、加工しない**。換算・集計はフェルミ推定で行い、計算はコードが担う(ast制限の四則演算+累乗)。出典の無いファクト・ナレッジは保存が拒否される。鮮度切れは `stale` として全レスポンスに付く。

---

## 見直す

```bash
medo requirements diff --project <id>            # 版間の差分と陳腐化した生成物
medo status --project <id> --view readiness      # なぜ次へ進めないか
medo fermi calc --project <id> --from-artifact fermi-v1   # 保存済みモデルで再計算
```

---

## Skillの再現性を測る

Skillは手順書であり、どのホストがどのモデルで実行するかで挙動が変わる。**事実はCLIが縛るが、Skillが必要な呼び出しを飛ばしたことは検出できない** — 飛ばしても残りは正常終了するため。

状態がすべてCLIにあるので、呼び出し列は決定論的な成果物になる。同じ初期状態から各ホストに1周させ、トレースを突き合わせる。

各ホストで `MEDO_TRACE` にファイルパスを渡して1周させる。指定したファイルにJSONLが追記される。

```bash
MEDO_TRACE=/tmp/claude.jsonl  medo status --project <id>   # Claude Code で1周
MEDO_TRACE=/tmp/gemini.jsonl  medo status --project <id>   # agy で同じ初期状態から1周
```

突き合わせは呼び出し列だけを取り出して行う(`jq` があれば `jq -c '{command,options,exit_code}'` でも同じ)。

```bash
extract() { python3 -c "
import json,sys
for line in open(sys.argv[1]):
    e = json.loads(line)
    print(e['command'], e['options'], e['exit_code'])
" "$1"; }
diff <(extract /tmp/claude.jsonl) <(extract /tmp/gemini.jsonl)
```

値が残るのは**どの選択をしたかを表すオプション**だけである。選択肢(`--result` / `--reaction` / `--outcome` 等)と、案件内で閉じた参照ID(`--artifact` / `--stakeholder` / `--responds-to` / `--focus` 等)は残る。**自由文(`--statement` / `--note` 等)・ファイルパス・案件ID(`--project`)は `<redacted>` になる**ため、顧客の生の声や顧客名を含むパスはトレースに残らない。

```json
{"command": ["respond", "add"],
 "options": {"--project": "<redacted>", "--stakeholder": "sh-1",
             "--artifact": "as-is-report-v1", "--purpose": "as_is_alignment",
             "--reaction": "acknowledged", "--note": "<redacted>"},
 "exit_code": 0}
```

---

## 環境変数

| 変数 | 既定 | 用途 |
|---|---|---|
| `MEDO_BACKEND` | `local` | ストレージ切替(`local` / `firestore`) |
| `MEDO_HOME` | `~/.medo` | localバックエンドのデータルート |
| `MEDO_TRACE` | (なし) | 設定するとCLI呼び出し列をJSONLで追記 |
