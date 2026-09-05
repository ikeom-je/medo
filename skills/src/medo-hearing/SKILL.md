---
name: medo-hearing
description: 業界・ビジネス状況・課題・経営思想/方針をヒアリングとブレストで構造化し、medoの要件ドキュメント(バージョン付き)として保存する。課題も要件も最初から確定しない前提で、confidenceとopen_questionsを育てる。
---

# medo-hearing: 課題と方針を構造化する

あなたは上流工程のビジネス課題整理を支援する。ユーザーの話・ヒアリングメモ・参考資料から、システム要件に直行せず、まず業界・ビジネス状況・課題・経営思想を構造化する。

## 進め方

0. プロジェクトIDが既に決まっている場合は `medo status --project <project-id>` を実行し、現在地(要件バージョン・ファクト・生成物・next_step)をユーザーに報告してから始める。
1. ユーザーの入力を読み、まず理解した内容を1段落で要約して確認する。
2. 次を一つずつ質問して埋める(すでに分かっている項目は聞かない):
   - industry / background: 業界と、そのビジネス状況の要約(市場環境・競合・業務の現状)
   - challenges: 課題(What/Whyの起点)。各項目に confidence を付ける
     - confirmed: ユーザーが明言した / assumed: 文脈からの推定 / open: 要検討
   - principles: 経営思想・理念・方針。**これは検索で調べる事実ではなく、ヒアリングとブレストで引き出して合意する対象**。「何を大切にしたいか」「どんな会社でありたいか」を対話し、ブレストで言語化を手伝い、合意した文言だけを confirmed にする
   - goal: 現時点のやりたいことの一文(打ち手の合意とともに変わってよい)
   - functional / non_functional: 既に見えているシステム要件があれば(薄くてよい。打ち手合意後に育てる)
3. 確認できなかった事項・判断に効く未確定事項は、勝手に埋めずに open_questions に残す。
4. 以下のYAMLを作り、ユーザーに見せて確認を取ってから保存する。

## 保存

要件YAMLを一時ファイル(例: /tmp/req.yaml)に書き、次を実行する:

    medo requirements save --project <project-id> --file /tmp/req.yaml

- project-id はユーザーと合意した英数字slug(例: yoyaku-system)
- 保存後、`saved: v<n>` の出力をユーザーに伝える
- 2回目以降の保存は自動的に新バージョンになる。保存後に `medo requirements diff --project <project-id>` を実行し、差分と陳腐化した生成物を報告する
- 終了時、対話から得た案件固有ノウハウがあれば次で追記する:

      medo knowledge save --project <project-id> --statement "<案件固有ノウハウ>" --source "medo-hearing <日付>対話"

  フェーズ1では追記のみ行い、既存エントリとの統合・重複解消はしない。
- 最後に `medo status --project <project-id>` を実行し、現在地と次ステップ(next_step)を報告して終える

## YAMLスキーマ

    project: <slug>
    industry: <業界>
    background: <業界・ビジネス状況の要約>
    goal: <一文>
    principles:
      - text: <経営思想・理念・方針>
        confidence: confirmed | assumed | open
    challenges:
      - text: <課題>
        confidence: confirmed | assumed | open
    functional:
      - text: <機能要件>
        confidence: confirmed | assumed | open
    non_functional:
      performance: <値>
      budget_cap: <値>
    open_questions:
      - <未確定事項>
    sources:
      - <ヒアリングメモや参考URLの出所>

## 契約(必ず守る)

- CLIが失敗したら(非ゼロ終了)、推測で補完せずエラー内容をそのまま報告する
- 開始時(プロジェクトIDが分かる場合)と終了時に `medo status` を実行し、現在地と次ステップを報告する
- 終了時、対話から得た案件固有ノウハウがあれば `medo knowledge save --project <id> --statement "..." --source "medo-hearing <日付>対話"` で追記する。フェーズ1では追記のみ行い、統合・重複解消はしない
- ユーザーが言っていないことを confirmed にしない。principles はユーザーが合意した文言だけを書く
- 課題の妥当性への意見(見落とし・深掘りの提案)は述べてよいが、本文はユーザーの合意した内容だけを書く
