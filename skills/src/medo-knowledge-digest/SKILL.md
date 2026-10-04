---
name: medo-knowledge-digest
description: 案件を跨いで蓄積したナレッジの重複を洗い出し、ユーザーが承認した組だけを置き換えて来歴を残す。値の食い違いは統合せずに見せる。標準周回とは別の保守作業。
---

# medo-knowledge-digest: ナレッジの重複を統合する

重複の判定はJevの分類とCLIの決定論で行い、確定はユーザーの承認とCLIで行う。
このSkillは新しい文を書かない。既存エントリのどちらかを残す。

## 手順

1. 全体を見る:

       medo knowledge index

   `warning:` があれば(来歴の破損)そのまま報告する。

2. kind ごとに統合案を作る(書き込みはしない):

       medo knowledge dedupe --kind <tech|market|policy|trend|company|practice>

   `judge: unavailable` なら、`candidate:` の組を見せて「判定できなかった」と報告し、統合はしない。

3. 結果をユーザーに見せる。どの区分でも、分類・確信度に加えて、組の両方を `medo knowledge get --kind <k> --id <id>` で取得し本文と出典を示す。
   - `proposals`(統合案)は、置き換える側 -> 残す側と理由を並べる
   - `conflicts`(値の食い違い)は統合せず、**ユーザーが出典を開いて確認するよう案内する。自分で出典を読んで解決しに行かない**
   - `held`(判定保留)は見せるだけでよい

4. `proposals` を**1組ずつ**ユーザーに承認を尋ね、返答を待ってから確定する:

       medo knowledge supersede --kind <k> --old <置き換える側> --by <残す側> --reason <duplicate|updates>

   承認されなかった組は確定しない。`held` の組は、ユーザーが根拠を見て統合したいと明言したときに限り、残す側と理由をユーザーに確かめてから確定してよい。

5. `supersede` の出力の `affected:` を集め、作り直しが要る生成物として案件ごとに報告する(各案件の `medo status` の `regenerate_stale_artifacts` にも載る)。

## 契約(必ず守る)

- 確定は `medo knowledge supersede` だけで行い、エントリのファイルを直接書き換えない
- ユーザーの承認なしに置き換えない。`conflicts` を統合しない
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
