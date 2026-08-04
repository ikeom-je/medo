---
name: medo-grow-prfaq
description: 合意した打ち手を完全版PRFAQ(技術的背景・workflow改善見込み・効果・ロードマップ付き)に育成して保存する。技術的背景はナレッジ根拠に縛り、育成元(grown_from)を記録する。
---

# medo-grow-prfaq: 合意した打ち手を完全版PRFAQに育てる

ミニPRFAQ候補セットから合意された打ち手を、顧客に持ち帰れる完全版PRFAQに育成する。

## 進め方

1. 現在地を確認し、ユーザーに報告する:

       medo status --project <project-id>

   `next_step` が `propose-options` なら「まず medo-propose-options で候補を作る」よう案内して終了する。
2. **どの打ち手に合意したかをユーザーに確認する**(合意はツールの外の意思決定。勝手に選ばない)。
3. 育成元の候補セットと要件を取得する:

       medo artifacts get --project <project-id> --id <mini-prfaq-vN>
       medo requirements get --project <project-id> --format json

4. 技術的背景を深めるためナレッジを検索し(`medo knowledge search`)、必要に応じてファクトを追加保存する。
5. 完全版PRFAQを作る。ミニPRFAQの内容に加えて:
   - 技術的背景(実装手段の技術的な要点。引用したナレッジエントリのkind・statementに基づき、絵に描いた餅にしない)
   - workflow改善見込み(現状業務がどう変わるか)
   - 効果(フェルミ推定の引用。必要なら `medo fermi calc` で追加計算)
   - ロードマップ(段階と、open_questionsが各段階に与える影響)
   - FAQ(顧客・社内から想定される問いと答え)
6. 保存する:

       medo artifacts save --project <project-id> --type prfaq \
         --file /tmp/prfaq.md \
         --grown-from "<mini-prfaq-vN>:<合意した打ち手名>" \
         --cites <entry-id,...> --cites-facts <fact-id,...> \
         --generated-by <claude|gemini> --requirements-version <n>

7. 終了時、対話から得た案件固有ノウハウがあれば次で追記する:

       medo knowledge save --project <project-id> --statement "<案件固有ノウハウ>" --source "medo-grow-prfaq <日付>対話"

   フェーズ1では追記のみ行い、既存エントリとの統合・重複解消はしない。
8. 保存後 `medo status --project <project-id>` を実行し、現在地と次ステップを報告して終える。

## 契約(必ず守る)

- 技術・サービス能力の有無はナレッジ値のみ。市場数値は保存済みファクトのみを引用する
- stale なファクト・ナレッジエントリを使う場合は必ず注記する
- 打ち手の選択(合意)を自分で行わない。ユーザーの確認を必ず取る
- `--grown-from` に育成元の候補セットIDと打ち手名を必ず記録する
- 終了時、対話から得た案件固有ノウハウがあれば `medo knowledge save --project <id> --statement "..." --source "medo-grow-prfaq <日付>対話"` で追記する。フェーズ1では追記のみ行い、統合・重複解消はしない
- CLIが失敗したら推測で補完せずエラー内容を報告する
