---
name: medo-decide
description: 顧客の反応とレビュー所見を要件ドキュメントに反映し、その周回で新たに分かったことを確認して、往復を続けるか次の段階へ進むかを判断する。ToBeチェックポイントへの回答も行う。標準周回のステージ4(振り返る・次へ進む)。
---

# medo-decide: 振り返る・次へ進む

**回ること自体が価値**である。チェックリストが埋まらなくても、周回を重ねること自体が解像度を上げる。

## 進め方

1. 現在地とその周回の成果を読み、ユーザーに報告する:

       medo status --project <project-id> --view summary
       medo status --project <project-id> --view workflow

   `workflow.loop.round_delta` が今回新たに分かったこと。`progress_count` が
   0 でなければ前進している。`divergence_warning` が真なら2周続けて成果ゼロで
   あり、論点の立て方をユーザーと見直す。
   `workflow.responses.effective` が有効な反応の一覧。

2. 反応と所見を要件に反映する。現在の要件を取得して編集する:

       medo requirements get --project <id> --format json > /tmp/req.json

   - `objected` / `unclear` の反応が指す内容を `as_is` / `to_be` などに反映する
   - 確認が取れた項目の `confidence` を上げる(`open` → `assumed` → `confirmed`)
   - **既存ノードの id は書き換えない**。書き換えると過去のイベント・生成物の
     参照が別のノードを指す
   - 真因が確定したら `bottlenecks` に置く。**`confirmed` のみ保存できる**ため、
     未検証のうちは `hypotheses`(`kind: cause`)に置いたままにする
   - 矛盾・判断不能が「解くべき課題」だと分かったら `challenges` に追加し、
     `promoted_from` に昇格元(`kind` と `ref`)を記録する

3. 保存する。誤字・言い回しの修正だけのセクションは `--editorial <section>` を付ける:

       medo requirements save --project <id> --file /tmp/req.json

   保存すると節目(`MilestoneDetected`)が自動で記録されることがある。

4. 節目が未回答なら回答する。`actions` の先頭が `answer_tobe_checkpoint` になる:

       medo checkpoint answer --project <id> --responds-to <ev-N> \
         --answer <generate|defer> --focus <hyp-N>

   `--focus` はその周回で検証したい仮説を1つ選ぶ。**これが無いと蓄積した課題と
   GAPすべてに一律で向き合うことになり、周回が発散する**。

5. 差分と陳腐化した生成物を確認する:

       medo requirements diff --project <id>

6. 終了時に現在地を読み、`actions` を報告する:

       medo status --project <id> --view summary

   - `readiness.state` が `ready` なら「収束条件を満たした。medo-propose-options で
     打ち手候補に進める」と案内する
   - そうでなければ「次の周回を medo-investigate から回す」と案内する
   - 詳しい理由が要るときだけ `medo status --view readiness` を呼び、
     `failed_conditions` を報告する

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions` をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
