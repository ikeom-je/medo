---
name: medo-dialogue
description: レビュー済みの討議用スライドを顧客に提示する準備を整え、得られた確認・共感・異議をステークホルダーごとの反応として記録する。標準周回のステージ3(ぶつける・反応を得る)。
---

# medo-dialogue: ぶつける・反応を得る

**提示と反応の記録に専念する**。資料の生成は medo-investigate、検証は medo-review が済ませている。

## 進め方

1. 現在地を読み、提示できる状態か確認する:

       medo status --project <project-id> --view summary
       medo status --project <project-id> --view workflow

   - `workflow.review.approved` が `false` なら、まだ内部検証を通していない。
     medo-review を先に回すかをユーザーに確認する(**止めはしない**)
   - `workflow.review.open_findings` が空でなければ未解決の所見が残っている。
     そのまま提示するか先に直すかをユーザーに確認する
   - `workflow.loop.focus_hypothesis` がその周回で検証したい論点

2. 提示する討議用スライドを読む。IDは `medo artifacts list` で確認する
   (`workflow.review.current_target` が返すのは as-is-report のIDだけ):

       medo artifacts list --project <id>
       medo artifacts get --project <id> --id <slides-vN>

   章3(立場による見え方の違い)を含む場合、**提示相手に応じた開示制御をユーザーに問う**。
   対立当事者が同席する合同会議では出さず、個別のすり合わせで扱う。

3. 章6の問いを、その周回の `focus_hypothesis` に絞って読み上げられる形に整理して渡す。
   顧客に確認する項目は次で取れる:

       medo check list --confirmer customer

4. 得られた反応を、**ステークホルダーごとに1件ずつ**記録する。`sh-N` は
   `medo requirements get --project <id> --format json` の `stakeholders` が返す。
   **purpose によって対象の指定が変わる**:

   現状認識への反応(対象は as-is-report):

       medo respond add --project <id> --stakeholder <sh-N> \
         --artifact <as-is-report-vN> --purpose as_is_alignment \
         --reaction <empathized|acknowledged|agreed|objected|unclear> \
         --note "<相手の言葉に近い形で>"

   理想像を進めてよいかの返答(対象は要件。**`--artifact` を付けない**):

       medo respond add --project <id> --stakeholder <sh-N> \
         --purpose to_be_go_ahead \
         --reaction <empathized|acknowledged|agreed|objected|unclear> \
         --note "<相手の言葉に近い形で>"

   `unclear` は「反応が読み取れなかった」であり失敗ではない。沈黙や曖昧な同意を
   `agreed` に丸めない。要件の訂正・追加はここでは記録に留め、反映は medo-decide が行う。

5. 顧客が答えたチェック項目を記録する。**artifact束縛の項目は `--artifact` が必須**
   (`medo check list` の `binding` を見る):

       medo check add --project <id> --check as_is_articulation \
         --result <completed|finding|undeterminable> --artifact <as-is-report-vN> \
         --note "<顧客の反応>"

   「あるべき姿がまだ描けない」「判断できない」という反応は
   `--result undeterminable --disposition open` で記録する。**それ自体が発見**である。

6. 終了時に現在地を読み、`actions` を報告する:

       medo status --project <id> --view summary

   「次は medo-decide で反応を要件に反映し、往復継続か次段階かを判断する」と
   案内して終える。

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions` をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
