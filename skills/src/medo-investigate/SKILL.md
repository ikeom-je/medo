---
name: medo-investigate
description: 業界・ビジネス状況・現場の実態をヒアリングと調査で構造化し、出典付きファクトと要件ドキュメントとして保存する。必要なら現状調査・分析報告書と、顧客にぶつける討議用スライドまで作る。標準周回のステージ1(調べる・仕立てる)。
---

# medo-investigate: 調べる・仕立てる

公開情報と顧客の生の声を集め、現状を整理する。**手順6で終えてもよい**。報告書とスライドは顧客にぶつける段で作る。

## 進め方

1. 現在地を読み、`actions`(次にできること)をユーザーに報告する:

       medo status --project <project-id> --view summary   # 未作成なら次はID合意

2. 調査を計画する。**掘る目的・停止条件・取得規範はCLIが返す**:

       medo status --project <id> --view model
       medo research plan --project <id> --depth <scan|structural|deep>

   `model.links` / `model.coverage` の未解消項目が埋める対象。既定は structural。

3. **自分の検索能力で**観点ごとに検索し、結果を候補JSONにして選別にかける。
   **表面的な検索結果で止めない**:

       medo research triage --project <id> --file /tmp/cands.json --opened <n>

   候補は `[{"url","title","snippet","hop"}]`。`open` の順に開き、新リンクを次の
   候補にして繰り返す。`diminishing_returns` で打ち切り、`judge: unavailable` なら
   **選別が効いていないと報告する**。国の施策は `--depth deep` で一次資料まで辿る。

4. 効いたファクトを保存する。数値は出典に忠実に転記し加工しない。ヒアリング
   由来は `--kind company --source "ヒアリング(<日付> <相手>)"`:

       medo facts save --project <id> --kind <market|policy|trend|company> \
         --statement "<出典の記述に忠実な一文>" --source <出典URL> \
         --value <数値> --unit <単位> --retrieved <YYYY-MM-DD>

5. 要件の雛形を埋める(既存案件は `requirements get --format json` の出力を編集。
   **既存ノードの id は書き換えない**):

       medo requirements template > /tmp/req.yaml

   例はコメントアウト済み。**埋める項目だけ外す**。埋まらない項目は
   `open_questions` に置くか何も書かない。勝手に埋めない。

6. 保存する(誤字だけの修正は `--editorial <section>`)。
   **調査の初期はここで終えてよい**。次に何を確かめるかをユーザーと決める:

       medo requirements save --project <id> --file /tmp/req.yaml
       medo status --project <id> --view summary

7. 共有する段で現状調査・分析報告書を保存する(調査ノートは `--type research`
   で先に保存し `--derived-from` で繋ぐ):

       medo artifacts save --project <id> --type as-is-report --cites-facts <id,...> \
         --requirements-version <n> --generated-by <who> --file /tmp/as-is-report.md

8. 討議用スライドを作る。**章構成と規約はCLIが返す**(`workflow.loop.focus_hypothesis`
   が章0、`workflow.checks.states` が章6に要る):

       medo status --project <id> --view workflow
       medo artifacts outline --type slides --slide-kind discussion
       medo artifacts save --project <id> --type slides --slide-kind discussion \
         --derived-from as-is-report-v<n> --requirements-version <n> \
         --generated-by <claude|codex|gemini> --file /tmp/slides.md

9. 終了時に現在地を読み `actions` を報告し、得たノウハウがあれば追記する:

       medo status --project <id> --view summary
       medo knowledge save --project <id> --statement "<ノウハウ>" \
         --source "medo-investigate <日付>対話"

   スライドまで作れたら「次は medo-review で内部検証」と案内して終える。

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions`(案件が未作成なら `next_step`)をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
