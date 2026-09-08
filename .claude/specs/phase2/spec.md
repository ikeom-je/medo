# フェーズ2 spec(Agent用要約)

> 正本: `docs/superpowers/specs/medo-phase2-design.md`(索引)と、その配下の詳細6本。
> 実装計画: `docs/superpowers/plans/medo-phase2-core.md`(優先度1〜4)。
> このファイルはAgentが作業時に参照する要約。設計変更時は正本を先に更新し、本ファイルを同期する。

## 正本の索引

いずれも `docs/superpowers/specs/` 配下。

| 詳細 | ファイル |
|---|---|
| ドメインモデル(ノード型・ID規約・変更manifest) | `phase2-domain-model.md` |
| ワークフローモデル(イベント・畳み込み・収束規則) | `phase2-workflow-model.md` |
| status契約(診断の階層・projection・JSON) | `phase2-status-contract.md` |
| 生成物のライフサイクル(依存グラフ・陳腐化・カバレッジ) | `phase2-artifact-lifecycle.md` |
| スライド設計(討議用 / 最終提案) | `phase2-slides-design.md` |
| Skill構成と移植性 | `phase2-skill-portability.md` |

## ゴール

フェーズ1で通した「What/Whyの合意形成」を、**利用者が漏れなく重複なく進められるよう導く**支援に踏み込む。medoは利用者を導く支援ツールであり、判断を代行しない。

## 標準周回(4ステージ)

暗黙知はAsIsとToBeを何度も往復して初めて出てくる。往復は頭の中では回らず、**各ステージで成果物を出し、レビューし、顧客にぶつけて反応を得る**ことで進む。

| Stage | 保存するもの | 主なCLI操作 | 次の判断材料 |
|---|---|---|---|
| 1. Investigate & Draft(調べる・仕立てる) | `facts` / `RequirementsDoc.as_is` / `research` / `as-is-report` / **討議用 `slides`** | `facts save` / `requirements save` / `artifacts save` | `model.coverage` |
| 2. Internal Review(内部検証) | `AsIsReportReviewed` | `medo review add` | `workflow.review` |
| 3. Client Dialogue(ぶつける・反応を得る) | `StakeholderResponded` | `medo respond add` | `workflow.responses` |
| 4. Adapt & Decide(振り返る・次へ進む) | 要件の新版 / `ToBeCheckpointRecorded` | `requirements save` / `medo checkpoint answer` | `readiness` / `actions` |

**固定の状態機械ではない**。どのステージから始めても成立し、CLIは順序を強制せず現在地だけを返す。討議用スライドはステージ1で作る(顧客に投影する資料こそ内部レビューを通す)。

周回ごとに `focus_hypothesis_id` を1つ選び、その周回の顧客対話はそれを検証することに集中する。**回ること自体が価値**であり、`round_delta`(今回新たに分かったこと)を返して進捗を可視化する。「顧客があるべき姿を語れないと分かった」ことも成果として数える。

## 不変条件

フェーズ2の設計変更で**変えてはならない**もの。

1. **数値・事実の通り道にLLMを挟まない**。保存済みの値の参照・計算・鮮度判定はコードが行う
2. **課題も要件も最初から確定しない**。確度は `confidence` で表し、進行制御(ゲート)で表さない
3. **自律的なmulti-agentを採らない**。会話Agentは1体(ホストLLM)+決定論的ツール群
4. **medoはコマンドラインツールである**。Skillは手順書であり、実行主体は常にホストLLM。medo自身はAgentにならない
5. **認証・マルチテナントを導入しない**(利用スコープは本人のみ)
6. **診断は報告であって強制ではない**。未接続・未確認・未解決を検出しても保存を拒否しない
7. **厳密さは事実の層に、寛容さはプロセスの層に**。出典必須・数値の通り道にLLMを挟まない・鮮度判定は一切緩めない。一方、チェックが埋まらなくても・矛盾が残っていても**進行は止めない**。これを混同すると「一緒に考える」が「根拠なく描く」に滑る

## スコープ(本計画=優先度1〜4)

決定論層のみ。`medo_core` に `nodes` / `watermark` / `manifest` / `events` / `workflow` / `checks` / `responses` / `diagnostics` / `context` を追加し、`artifacts` と `status` を拡張。CLIに `check add` / `review add` / `respond add` / `checkpoint answer` と `status --view` を追加する。

## スコープ外(優先度5以降・別計画)

Skill 4本・討議用スライド生成(優先度5)、最終提案スライド+`phase_signoff` ゲート(優先度6)、出典検証の強化(並行)。ナレッジ来歴 / `knowledge-digest` / `decision-roadmap` / `build-mock` / `propose-architecture` / pricing / 簡易Webアプリは**詳細設計が未了**で、着手前に設計ドキュメントを起こす。

## 読み取れないものだけ書く(実装とstructure.mdを見れば分かることは書かない)

- **ID採番簿はプレフィックス別の high-water mark を持ち、削除済みIDを再利用しない**。ノードIDは案件内で永続的な同一性を表すため、詰め直すと過去のイベント・生成物の参照が別のノードを指す(値の一覧は `medo_core.nodes.ID_PREFIXES`)
- **陳腐化は `stale`(要再生成)と `outdated`(差分確認推奨)の2段階**。`text` 変更は既定で `stale` であり、保存時に `change_kind: "editorial"` を**明示宣言したときだけ** `outdated` に落ちる。core は宣言を決定論的に処理するだけで、意味差を推測しない
- **`next_step` はフェーズ1の値域を完全一致で維持する**。フェーズ1のSkillが値で分岐しているため、`actions` の新しい値域を流し込んではならない
- **`.claude/steering/` はフェーズ2の追加分をまだ反映していない**。`structure.md` §5 のストレージパス表に `projects/{id}/events/{ev_id}` / `manifests/v{n}` / `meta/id_watermark` は無く、`tech.md` §5 の環境変数表に `MEDO_TRACE` も無い。モジュール一覧も更新されていない。これらは実装(`core/src/medo_core/` / `cli/src/medo_cli/`)と正本 `phase2-domain-model.md` を正とする
