---
name: medo-investigate
description: 業界・ビジネス状況・現場の実態をヒアリングと調査で構造化し、出典付きファクトと要件ドキュメントとして保存する。必要なら現状調査・分析報告書と、顧客にぶつける討議用スライドまで作る。標準周回のステージ1(調べる・仕立てる)。
---

# medo-investigate: 調べる・仕立てる

公開情報と顧客の生の声を集め、現状を整理する。**手順4で終えてもよい**。報告書とスライドは、顧客にぶつける段になってから作る。

## 進め方

1. 現在地を読み、`actions`(次にできること)をユーザーに報告する:

       medo status --project <project-id> --view summary

   案件が未作成なら `actions` は返らず `next_step: hearing` になる。その場合は
   ユーザーと英数字slugのIDを合意してから進む。

2. 業界・市場・国策・業界動向を検索し、判断に効くファクトを保存する:

       medo facts save --project <id> --kind <market|policy|trend|company> \
         --statement "<出典の記述に忠実な一文>" --source <出典URL> \
         --value <数値> --unit <単位> --retrieved <YYYY-MM-DD>

   数値は出典に忠実に転記し、加工しない。ヒアリング由来の個社情報は
   `--kind company --source "ヒアリング(<日付> <相手>)"`。自分の検索能力を使う。

3. 要件の雛形を取得して埋める:

       medo requirements template > /tmp/req.yaml

   既存案件を更新するときは代わりに `medo requirements get --project <id> --format json`
   の出力を編集する。**既存ノードの id は書き換えない**。
   雛形の例はコメントアウトされている。**埋める項目だけコメントを外す**。
   埋まらない項目は `open_questions` に置くか、何も書かない。勝手に埋めない。

4. 保存する。誤字・言い回しの修正だけのセクションは `--editorial <section>` を付ける:

       medo requirements save --project <id> --file /tmp/req.yaml
       medo status --project <id> --view summary

   **調査の初期はここで終えてよい**。`actions` を報告し、次に何を確かめるかをユーザーと決める。

5. 共有する段になったら、現状調査・分析報告書を書いて保存する:

       medo artifacts save --project <id> --type as-is-report \
         --requirements-version <n> --generated-by <claude|codex|gemini> \
         --file /tmp/as-is-report.md --cites-facts <fact-id,...>

   内部の調査ノートを別に残す場合は `--type research` で先に保存し、
   `as-is-report` に `--derived-from research-v<n>` を付ける。

6. 討議用スライドを作る。**章構成と表現の規約はCLIから取得する**:

       medo status --project <id> --view workflow
       medo artifacts outline --type slides --slide-kind discussion

   `workflow.loop.focus_hypothesis` が章0、`workflow.checks.states` が章6に要る。
   出力に従って `/tmp/slides.md` を書き、保存する:

       medo artifacts save --project <id> --type slides --slide-kind discussion \
         --derived-from as-is-report-v<n> --requirements-version <n> \
         --generated-by <claude|codex|gemini> --file /tmp/slides.md

7. 終了時に現在地を読み、`actions` を報告する:

       medo status --project <id> --view summary

   対話から得た案件固有ノウハウがあれば追記する:

       medo knowledge save --project <id> --statement "<ノウハウ>" \
         --source "medo-investigate <日付>対話"

   スライドまで作れたら「次は medo-review で内部検証」と案内して終える。

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions`(案件が未作成なら `next_step`)をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
