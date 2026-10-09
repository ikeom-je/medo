---
name: medo-propose-options
description: 要件ドキュメント(課題・方針)を起点に、市場・国策・業界動向ファクトとフェルミ推定に裏づけられた打ち手候補(2〜3案)を生成し、ミニPRFAQ候補セットとして保存する。事実はCLIが検証・保存した出典付きファクトとナレッジ値に縛る。
---

# medo-propose-options: 打ち手候補をミニPRFAQで比較可能にする

要件ドキュメントを入力に、ビジネスの打ち手候補を2〜3案生成する。発想は自由に、事実はファクトとナレッジに縛る。

## 進め方

1. 現在地を読み、`actions`(次にできること)をユーザーに報告する:

       medo status --project <project-id> --view summary

   `next_step` が `hearing` なら「まず medo-investigate で現状を構造化する」よう
   案内して終了する。続けて最新要件を取得する:

       medo requirements get --project <project-id> --format json

2. 市場・国策・業界動向を検索し(自分の検索能力を使う)、案件の判断に効くファクトを保存する:

       medo facts save --project <project-id> --kind <market|policy|trend> \
         --statement "<出典の記述に忠実な一文>" --value <数値> --unit <単位> \
         --source <出典URL> --retrieved <取得日YYYY-MM-DD> --quote "<原文の一文>"

   - kind は market=市場規模・需要・価格・シェア / policy=法令・国の計画・補助金 / trend=業界・技術・社会の動向と統計の推移(出典の主体や予測か否かではなく記述対象で選ぶ。市場規模・需要の推移や予測は market、人口などの社会統計は trend)
   - **数値は出典に忠実に転記し、加工しない**(換算・集計が必要ならフェルミ推定で行う)。`--quote` は出典本文をそのまま写した最小の一文(`--value` を付けるならその数値を含め、表なら単位見出しも含める。`--unit` は抜粋の表記を単複も含めそのまま書き、日本語の説明は任意で末尾に括弧1つで添える(例: `tools(ツール数)`)。複数語の単位・前置の通貨記号・k/M の略記・英語の単位見出しは照合できないので `--unverifiable-reason` を使う。定性ファクトは `--value` / `--unit` を省く)。拒否されたらエラーの「次の手」で直して再実行し、解決しなければエラーをそのまま報告する
   - 既存ファクトを引用する前に `medo facts list --project <project-id>` で `[UNVERIFIED]` / `[LEGACY]` / `[DOUBTFUL]` を確かめる。`[LEGACY]` / `[UNVERIFIED]` は出典を読んで `medo facts verify --project <project-id> --fact <fact-id> --quote "<原文の一文>"` で再検証し、出力が `verified:` のときだけ検証済みとして引用する(`unverified:` や拒否なら注記して引用する)
   - ヒアリング由来の個社情報は `--kind company --source "ヒアリング(<日付> <相手>)"` で保存する
   - 出典のないデータは保存も引用もしない

3. 効果・市場規模の桁感をフェルミ推定で計算する。モデルYAML(variables: fact参照 or assume、formula)を一時ファイルに書き:

       medo fermi calc --project <project-id> --file /tmp/model.yaml

   - 仮定(assume)は明示し、計算は自分でしない(CLIのコードが計算する)
   - 将来予測は policy/trend ファクトを成長率等の根拠に使う

   **フェルミ推定の計算を自分で行わない**。必ず `medo fermi calc` の結果を使う。

4. Howの目処のためナレッジを引く。**先に索引で「使えるものがありそうか」を見てから**
   実体を引く(複数回実行してよい。`truncated` が true なら絞って引き直す):

       medo knowledge index
       medo knowledge search "<キーワード>" --format json

5. 打ち手候補を**最低2つ・最大3つ**作る(1案に絞らない。決め手の仮説が外れたときの代わりになる)。メインとサブ(3つなら松・竹・梅)の役割を決める。切り口: **既存の解決 / 破壊的業務改革 / 新規市場開拓** × **スコープ / 立ち位置 / 根本治療vs対症療法**。各案のミニPRFAQに必ず含めること:
   - 打ち手の宣言(顧客に届いた未来のプレスリリース1段落)
   - 価値仮説(What/Why)。**principles(理念・方針)との整合を明記**
   - 効果の桁感(フェルミ推定の生成物IDと結果を引用)
   - Howの目処(ナレッジ根拠の要点。kind・statementと引用エントリID)
   - 主要リスク・open_questions
   - 策ごとの効果のフェルミ推定。モデルYAMLに `unit` を書き、策ごとに `medo fermi calc` で作る。**全策で同じ評価指標・期間・単位にし、大きいほど良い形で書く**(費用は効果から差し引く)。各 `assume` には根拠と尺度を `note` に書く
   - **策を分けるパラメタ**(結果しだいでどの策を取るかが変わる値。例: 利用率)。各策の推定でそれに当たる仮定の変数を決める。**変数はすべての策で同じ単位・尺度で書く**(0.3 と 30 を混ぜない)

6. **現在地を読み直す**。`actions` に `proceed_to_propose_options`、または
   `refs` に `mini-prfaq` を含む `regenerate_stale_artifacts` があれば保存する。
   どちらも無いなら**作る理由をユーザーに確認してから**作る — 鮮度を無視した
   作り直しは下流の引用関係とレビュー承認を壊す:

       medo status --project <project-id> --view summary
       medo artifacts save --project <project-id> --type mini-prfaq \
         --file /tmp/options.md \
         --options "<打ち手名>:<切り口>,<打ち手名>:<切り口>" \
         --tier "<打ち手名>=<main|sub|matsu|take|ume>" --option-fermi "<打ち手名>=fermi-vN" \
         --pivot "<パラメタ名>" --pivot-unit "<単位>" --pivot-var "<打ち手名>=<変数名>" \
         --cites <entry-id,...> --cites-facts <fact-id,...> \
         --generated-by <claude|codex|gemini> --requirements-version <n>

   策の効き目を左右する仮説には、要件の `hypotheses[].fermi_ref` に `artifact_id`(その策の fermi)と `variable_name`(パラメタの変数)を書いて保存する(切り替え点がその仮説の問いになる)。
   `--tier` / `--option-fermi` / `--pivot-var` は打ち手ごとに繰り返す。意味のある範囲があれば `--pivot-range <下限>,<上限>`(利用率なら `0,1`)。保存後に `medo status --project <project-id> --view uncertainty` で切り替え点(どの値を境にどの策が上になるか)と確かめるべき問いを読み、ユーザーに示す。

7. 終了時、対話から得たノウハウを追記する。**固有名詞を消して文が成り立つなら案件横断、
   成り立たないなら案件固有**に置く:

       medo knowledge save --project <project-id> --statement "<案件固有ノウハウ>" --source "medo-propose-options <日付>対話"
       medo knowledge save --kind practice --statement "<他案件でも使える型>" --source "medo-propose-options <日付>対話"

   追記のみ行い、既存エントリとの統合・重複解消はしない。
8. 保存後 `medo status --project <project-id> --view summary` を実行し、`actions` を
   報告する。「候補セットを比較・Q&Aし、合意した打ち手を medo-grow-prfaq で完全版に
   育てる」ことを案内して終える。

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions` をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目、および出典未検証(`[UNVERIFIED]` / `[LEGACY]`)・`[DOUBTFUL]` のファクトとそれを使った fermi 結果(`warning:` 行)を引用するときは、その旨を明記する
