---
name: medo-propose-options
description: 要件ドキュメント(課題・方針)を起点に、市場・国策・業界動向ファクトとフェルミ推定に裏づけられた打ち手候補(2〜3案)を生成し、ミニPRFAQ候補セットとして保存する。事実はCLIが検証・保存した出典付きファクトとナレッジ値に縛る。
---

# medo-propose-options: 打ち手候補をミニPRFAQで比較可能にする

要件ドキュメントを入力に、ビジネスの打ち手候補を2〜3案生成する。発想は自由に、事実はファクトとナレッジに縛る。

## 進め方

1. 現在地を確認し、ユーザーに報告する:

       medo status --project <project-id>

   `next_step` が `hearing` なら「まず medo-hearing で課題を構造化する」よう案内して終了する。
   続けて最新要件を取得する:

       medo requirements get --project <project-id> --format json

2. 市場・国策・業界動向を検索し(自分の検索能力を使う)、案件の判断に効くファクトを保存する:

       medo facts save --project <project-id> --kind <market|policy|trend> \
         --statement "<出典の記述に忠実な一文>" --value <数値> --unit <単位> \
         --source <出典URL> --retrieved <取得日YYYY-MM-DD>

   - **数値は出典に忠実に転記し、加工しない**(換算・集計が必要ならフェルミ推定で行う)
   - ヒアリング由来の個社情報は `--kind company --source "ヒアリング(<日付> <相手>)"` で保存する
   - 出典のないデータは保存も引用もしない

3. 効果・市場規模の桁感をフェルミ推定で計算する。モデルYAML(variables: fact参照 or assume、formula)を一時ファイルに書き:

       medo fermi calc --project <project-id> --file /tmp/model.yaml

   - 仮定(assume)は明示し、計算は自分でしない(CLIのコードが計算する)
   - 将来予測は policy/trend ファクトを成長率等の根拠に使う

4. Howの目処のためナレッジを検索する(複数回実行してよい):

       medo knowledge search "<キーワード>" --format json

5. 打ち手候補を2〜3案作る。切り口: **既存の解決 / 破壊的業務改革 / 新規市場開拓** × **スコープ / 立ち位置 / 根本治療vs対症療法**。各案のミニPRFAQに必ず含めること:
   - 打ち手の宣言(顧客に届いた未来のプレスリリース1段落)
   - 価値仮説(What/Why)。**principles(理念・方針)との整合を明記**
   - 効果の桁感(フェルミ推定の生成物IDと結果を引用)
   - Howの目処(ナレッジ根拠の要点。kind・statementと引用エントリID)
   - 主要リスク・open_questions

6. 全案を1つのmarkdown(候補セット)にまとめて保存する:

       medo artifacts save --project <project-id> --type mini-prfaq \
         --file /tmp/options.md \
         --options "<打ち手名>:<切り口>,<打ち手名>:<切り口>" \
         --cites <entry-id,...> --cites-facts <fact-id,...> \
         --generated-by <claude|gemini> --requirements-version <n>

7. 終了時、対話から得た案件固有ノウハウがあれば次で追記する:

       medo knowledge save --project <project-id> --statement "<案件固有ノウハウ>" --source "medo-propose-options <日付>対話"

   フェーズ1では追記のみ行い、既存エントリとの統合・重複解消はしない。
8. 保存後 `medo status --project <project-id>` を実行し、「候補セットを比較・Q&Aし、合意した打ち手を medo-grow-prfaq で完全版に育てる」ことを案内して終える。

## 契約(必ず守る)

- 引用する市場数値・国策・業界動向は `medo facts` に保存済みの出典付きファクトのみ。技術・サービス能力の有無はナレッジ値のみ
- ファクト・ナレッジに `"stale": true` が付いたものを使う場合、文中に「(情報が古い可能性: <取得日>)」と必ず注記する
- フェルミ推定の計算をLLM(自分)で行わない。必ず `medo fermi calc` の結果を使う
- assumed/open の課題・要件に依存する判断には「要確認」の印を付ける
- 終了時、対話から得た案件固有ノウハウがあれば `medo knowledge save --project <id> --statement "..." --source "medo-propose-options <日付>対話"` で追記する。フェーズ1では追記のみ行い、統合・重複解消はしない
- CLIが失敗したら推測で補完せずエラー内容を報告する
