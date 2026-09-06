---
name: medo-review
description: 現状調査・分析報告書と討議用スライドを顧客に見せる前に内部検証し、論理矛盾・GAP・欠落と、顧客に見せてよいかの表現上の懸念を洗い出してレビュー結果を記録する。標準周回のステージ2(内部検証)。
---

# medo-review: 内部検証

顧客に出す前に論点を研ぐ。**このSkillは資料を作ったのとは別のホスト(Claude / Codex / agy)で実行してよい**。状態はすべてCLIにあるため、どのホストからでも同じ対象をレビューできる。

## 進め方

1. 現在地とレビュー対象を読む:

       medo status --project <project-id> --view summary
       medo status --project <project-id> --view workflow
       medo status --project <project-id> --view model

   `workflow.review.current_target` がレビュー対象の `as-is-report` ID
   (**summary にも model にも無い。workflow 枝を読む**)。
   対応する討議用スライドのIDは次で確認する:

       medo artifacts list --project <id>

   `model.links` と `model.coverage` が、繋がっていない要素と未検証の要素を返す。
   **これらは報告であって強制ではない**。埋まっていないこと自体を所見にしてよい。

2. 対象の本文を読む:

       medo artifacts get --project <id> --id <as-is-report-vN>
       medo artifacts get --project <id> --id <slides-vN>

3. 表現の規約を取得してスライドと突き合わせる:

       medo artifacts outline --type slides --slide-kind discussion

   章2・章3のリフレーミング規約に反する箇所、`internal_conflict` の開示制御が
   必要な箇所を所見にする。

4. 確認したチェック項目を記録する。何を確認すべきかは `actions` の `run_check` が、
   各項目の束縛は次が返す:

       medo check list

   `binding=artifact_bound` の項目(`source_quality` / `as_is_articulation` /
   `expression_safety`)は **`--artifact <対象ID>` が必須**で、無いと拒否される:

       medo check add --project <id> --check as_is_articulation \
         --result <completed|finding|undeterminable> --artifact <as-is-report-vN> \
         --refs <該当ノードID,...> --note "<所見>"

   `binding=persistent` / `version_bound` の項目は `--artifact` を付けない:

       medo check add --project <id> --check reality_gap --result completed --note "<所見>"

   判断できなかった項目は `--result undeterminable` で記録し、扱いを
   `--disposition open|deferred|promoted` で示す(既定 `open`)。
   **判断できなかったこと自体が発見**であり、隠さない。

5. レビュー結果を記録する:

       medo review add --project <id> --report <as-is-report-vN> --slides <slides-vN> \
         --outcome <approved|changes_requested> --reviewed-by <claude|codex|gemini|human> \
         --refs <要件側の所見ノードID,...> --slide-finding "<スライド固有の所見>"

   `--slides` は当該レポートから生成された討議用スライドである必要がある
   (CLIが検証する)。

6. 終了時に現在地を読み、`actions` を報告する:

       medo status --project <id> --view summary

   `approved` なら「次は medo-dialogue で顧客にぶつける」、
   `changes_requested` なら「medo-investigate で直して再生成する」と案内して終える。

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions` をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
