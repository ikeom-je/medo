---
name: medo-grow-prfaq
description: 合意案を完全版PRFAQに育て、最終提案スライドと実際に得たフェーズ承認の反応まで記録する。技術的背景はナレッジ根拠に縛る。
---

# medo-grow-prfaq: 合意案を最終提案と承認の記録まで育てる

合意した打ち手を完全版PRFAQと最終提案スライドに育て、意思決定者の反応を記録する。

## 進め方

1. 現在地を確認し、`actions`(次にできること)をユーザーに報告する:

       medo status --project <project-id> --view summary

   再実行時は成果物を作り直さず、`actions` に `complete_phase` があれば手順10へ、
   `request_phase_signoff` があれば手順9へ、`generate_final_slides` があれば手順7へ進む。
   いずれも無ければ手順2へ進む。`next_step` が `propose-options` なら、そのSkillを案内して終了する。
2. **どの打ち手に合意したかをユーザーに確認する**。勝手に選ばない。
3. 育成元の候補セットと要件を取得する:

       medo artifacts get --project <project-id> --id <mini-prfaq-vN>
       medo requirements get --project <project-id> --format json

4. `medo knowledge search` で技術的背景を深め、必要ならファクトを追加保存する。
   出力末尾のリフレーミング規約はPRFAQ本文にも適用する:

       medo artifacts outline --type slides --slide-kind discussion
5. 完全版PRFAQを作る。ミニPRFAQの内容に加えて:
   - 技術的背景(引用したナレッジのkind・statementに基づき、絵に描いた餅にしない)
   - workflow改善見込み(現状業務がどう変わるか)/ ロードマップ(段階とopen_questionsの影響)
   - 効果(フェルミ推定の引用。必要なら `medo fermi calc` で追加計算)
   - 採択案と却下案の比較観点・評価・選定理由(原則とKPIに紐づける)
   - FAQ(顧客・社内から想定される問いと答え)
6. 保存する:

       medo artifacts save --project <project-id> --type prfaq \
         --file /tmp/prfaq.md \
         --grown-from "<mini-prfaq-vN>:<合意した打ち手名>" \
         --rejected "<名前>:<理由>[:<受け入れたリスク>]" \
         --cites <entry-id,...> --cites-facts <fact-id,...> \
         --generated-by <claude|codex|gemini> --requirements-version <n>

   却下案が複数なら `--rejected` を繰り返す。
7. PRFAQをユーザーに提示し、修正を反映して確認を得る。確認前はスライドを生成しない。
8. **現在地を読み直す**。`generate_final_slides` は手順6でPRFAQが新しくなって初めて出る:

       medo status --project <project-id> --view summary

   無ければ作らない。`--view readiness` の `failed_conditions` を報告して手順10へ進む。
   あれば outline を取得し、その7章に沿って作る:

       medo artifacts outline --type slides --slide-kind final

   親は現行PRFAQちょうど1件とし、比較はPRFAQ本文から取り込む:

       medo artifacts save --project <project-id> --type slides --slide-kind final \
         --file /tmp/final-slides.md --derived-from <prfaq-vN> \
         --generated-by <claude|codex|gemini> --requirements-version <n>

   却下案はスライドのメタデータには付けない。
9. スライドを決裁者に提示し、`phase_signoff` を依頼する。**依頼だけでは記録しない**。
   反応が未取得ならその旨を報告し、手順10・11だけ実施して終える。得た反応だけを記録する:

       medo respond add --project <id> --stakeholder <sh-N> --artifact <slides-vN> \
         --purpose phase_signoff --reaction <reaction> --note "<得られた反応>"

   `<reaction>` は `empathized|acknowledged|agreed|objected|unclear` のいずれかを使う。
10. 対話から得た案件固有ノウハウがあれば追記する:

       medo knowledge save --project <project-id> --statement "<案件固有ノウハウ>" --source "medo-grow-prfaq <日付>対話"

   フェーズ1では追記のみ行い、既存エントリとの統合・重複解消はしない。
11. `medo status --project <project-id> --view summary` を再実行し、`actions` を報告して終える。

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions` をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
