# フェーズ2 生成物のライフサイクル

依存グラフ・陳腐化・カバレッジ。索引: [medo-phase2-design.md](medo-phase2-design.md)

---

## 1. 生成物の種別

```python
ArtifactType = Literal[
    "research", "as-is-report",                              # フェーズ2で追加
    "architecture", "slides", "mock", "comparison", "mini-prfaq", "prfaq", "fermi"
]
```

**`as-is-report` という名称にする**。要件ドキュメントのフィールド `as_is` と生成物が同名だと、どちらが正本か曖昧になる。

### 正本の責務を一方向に定める

| 層 | 役割 | 編集可能か |
|---|---|---|
| `facts` | 生の根拠(出典付き) | 追記 |
| `RequirementsDoc.as_is` | **構造化された現状認識の正本** | 更新する |
| `artifact: as-is-report` | 特定の要件バージョンから生成した、**共有用の不変スナップショット** | 再生成のみ |

**artifact本文から要件への逆同期はしない**。レビューや顧客の指摘で訂正が得られたら、**まず `RequirementsDoc.as_is` を更新し、その上で新しい `as-is-report` を再生成する**。markdownを直接編集して要件と乖離させない。

イベントの `target`([ワークフローモデル](phase2-workflow-model.md))は、**共有した不変スナップショット**(`as-is-report-vN`)を指す。どの時点の内容に対する反応かが一意に定まる。

### research は内部用

**顧客共有は `as-is-report` に一本化する**。実務では調査結果とAsIs分析は一体の「現状調査・分析報告書」として受け取られることが多く、複数の中間資料を顧客に読ませると混乱を招く。`research` は**エビデンスを集約する内部ノート**と位置づけ、顧客共有・レビュー・反応記録の対象は `as-is-report`(およびそのスライド)とする。

---

## 2. 依存グラフ

生成物は2種類の依存を持つ。

| フィールド | 意味 | stale伝播 |
|---|---|---|
| `grown_from` | **候補選択の来歴**(どの候補セットのどの打ち手を選んだか) | しない |
| `derived_from` | **内容依存の親**(複数可) | **する** |

```python
grown_from: GrownFrom | None = None      # prfaq のみ(既存・変更なし)
derived_from: list[str] = []             # 内容依存の親artifact ID(複数)
```

**単一親から複数依存へ広げる**。`as-is-report` は要件と `research` の両方を、`slides` は親レポートと未確定事項を入力にするなど、実際には複数入力を持つ。単一の任意親では、依存を書き忘れたときに陳腐化が伝播しない穴が残る。

### 子type × 親type × 必須性

**`slides` は用途を一級フィールドで持つ**。親typeからの推論に頼ると、複数の親を持てる設計では判別が曖昧になる。

```python
slide_kind: Literal["discussion", "final"] | None = None   # slides のみ必須
```

| 子type | `slide_kind` | 親type | cardinality |
|---|---|---|---|
| `as-is-report` | — | `research` | 0または1(その research の内容を使った場合は必須) |
| `slides` | `discussion` | `as-is-report` | **ちょうど1** |
| `slides` | `final` | `prfaq` | **ちょうど1** |

`slides` は `slide_kind` に対応する親を**ちょうど1つ**持つ。`discussion` と `final` の親を同時に持つことはできない。

**直接入力する生成物はすべて親に含める**。討議用スライドが `research` の内容を、最終提案スライドが `mini-prfaq` の比較結果を使う場合、それらは親 `as-is-report` / `prfaq` に**取り込まれている**ことを前提とする。取り込まずに直接参照する必要がある場合は、その生成物を親に追加する(cardinalityを緩める)判断をユーザーに確認する。

**依存は再帰的に評価され、連鎖して伝播する**:

```
research(cited_facts が stale)
   ↓ derived_from
as-is-report(親のstaleを継承)
   ↓ derived_from
slides(さらに継承)
```

### 実装契約

- `ArtifactStore.save` で以下を検証する(Pydantic単体ではStoreを参照できないため検証箇所はStore):
  - `derived_from` の各親が同一プロジェクトに実在し、上表の許容typeであること
  - `grown_from.artifact` が実在し、`grown_from.option` がその候補セットの `options` に存在すること
  - 循環参照でないこと
- `status` は**全Artifactを `id -> Artifact` で保持して親を再帰評価**してから、表示用に型ごと最新版へ射影する(型ごと最新版のみを保持すると、親が旧版のPRFAQだと解決できない)
- 親の欠落・循環参照は例外にせず、**理由付きで stale** とする
- CLIに `--derived-from <id,...>` を追加する

---

## 3. 型ごとの依存セクション

要件のどのセクションに依存するかを、**型ごとの固定ルール**として core が持つ(生成物側の宣言は不要)。

| 生成物type | 依存セクション |
|---|---|
| `fermi` | なし(facts と assume のみ) |
| `research` | なし(`facts` の引用のみ) |
| `as-is-report` | `as_is` / `gaps` / `constraints` / `stakeholders` / `attempts` |
| `mini-prfaq` | `goal` / `challenges` / `principles` / `constraints` / `to_be` / `kpis` |
| `prfaq` | 上記 + `as_is` / `gaps` / `bottlenecks` / `hypotheses` / `attempts` / `stakeholders` |
| `comparison` | `challenges` / `principles` / `constraints` / `kpis` |
| `slides`(`discussion`) | `open_questions` / `to_be` / `kpis`(親 `as-is-report` が依存しない範囲) |
| `slides`(`final`) | `open_questions`(親 `prfaq` が依存しない範囲) |
| `architecture` | `functional` / `non_functional` / `constraints` |
| `mock` | `functional` / `constraints` |

**`research` は要件セクションに依存しない**。調査結果は要件が変わっても陳腐化せず、引用ファクトの鮮度切れでのみ陳腐化する。ループの起点として要件の往復から独立していることを意味する。

**比較の基準**: 直前バージョンではなく、**`artifact.requirements_version` から最新版までの全変更manifest**([ドメインモデル](phase2-domain-model.md) §7)を畳み込んで評価する。途中に1つでも該当セクションの `substantive` な変更があれば `stale` とする。

### 生成主体の記録

```python
generated_by: Literal["claude", "codex", "gemini"] | None = None
```

**`codex` を追加する**。フェーズ2はどのホストからでも生成できる設計であり([Skill構成と移植性](phase2-skill-portability.md))、Codexが生成した成果物を記録できないと来歴が追えない。`fermi` はコードが生成するため `None` のまま。

レビューイベント([ワークフローモデル](phase2-workflow-model.md))も同様に `reviewed_by: Literal["claude", "codex", "gemini", "human"]` を持ち、誰がレビューしたかを追跡できるようにする。

---

## 4. 陳腐化の粒度

### 決定: セクション単位 + カバレッジ判定 + 2段階の重大度

実データ(medo-ops の v1→v2: 課題1件追加・open_question1件解決)で4パターンを比較した結果:

| 粒度 | 判定結果 | 評価 |
|---|---|---|
| 文書全体(フェーズ1現状) | 3件すべてstale | fermi は要件に依存しないのに誤検出 |
| **セクション単位** | 2件stale | 誤検出を解消。**採用** |
| ノード単位(依存のみ) | **0件stale** | 「課題の追加」を検出できず取りこぼす |
| ノード単位+カバレッジ | 2件stale | 正確だが安定IDの全面移行が必要 |

**ノード単位の依存追跡だけでは不十分**。追加は既存ノードを変更しないため依存グラフでは何も壊れないが、実際には「打ち手が全課題をカバーしていない」状態になる。

### 変更の種類による2段階判定

軽微な文言修正で下流の全生成物が連鎖的にstale化すると、実務で再生成ループに陥る。判定は決定論で行える。

| 対象 | `stale`(要再生成) | `outdated`(差分確認推奨) |
|---|---|---|
| **論理連鎖の中核ノード**(as_is / to_be / gaps / bottlenecks / challenges / constraints) | 追加・削除、`confidence` 変更、リンク変更、`evidence_refs` 変更、`AsIs.visibility` / `Gap.kind` / `scope` の変更、**`text` の変更** | `change_kind: "editorial"` を宣言した `text` 変更のみ |
| `stakeholders` | 追加・削除、`confidence` / `is_decision_maker` / `stance` / `influence` / `interest` / `surfaced_by` の変更 | `role` / `pains` / `text` の変更 |
| `Kpi` | 追加・削除、`current_fact_id` / `target_value` / `target_text` / `unit` / `to_be_ids` の変更 | `name` のみの変更 |
| `Hypothesis` | 追加・削除、`status` / `fermi_ref` / `challenge_ids` の変更 | `statement` / `validation_method` の変更 |
| `Attempt` | 追加・削除、`outcome` / `blocker` / `blocker_category` / `challenge_ids` / `gap_ids` / `confidence` / `evidence_refs` の変更 | `description` のみの変更 |
| `principles` / `functional` | 追加・削除、`confidence` 変更 | `text` のみの変更 |
| `non_functional`(dict) | キーの追加・削除、値の変更 | — |
| `open_questions` | 追加・削除、`scope` 変更 | `text` のみの変更 |
| `goal` | — | 変更 |
| `background` / `industry` / `sources` | — | 変更 |

**中核ノードの `text` 変更を既定で `stale` とする**。往復とは暗黙知が判明するたびにAsIsやToBeの本文を精緻化する工程そのものであり、それを「軽微」と分類すると意味が大きく変わった生成物が最新扱いのまま残る。特に `assumed → assumed` のまま複数周回する場合、`confidence` 変更でも捕捉できない。

誤字・言い回しの修正まで `stale` にしたくない場合は、**保存時に `change_kind: "editorial"` を明示的に宣言する**。core は宣言を決定論的に処理するだけで、本文の意味差をLLMや文字列差分から推測しない。宣言が無ければ `stale` を既定とする(安全側に倒す)。

**`Attempt.blocker` を `stale` 側に置く理由**: 頓挫理由は「なぜ今まで解決していないか」の核心であり、生成物の記述を実質的に変える。`description`(何をやったか)の言い換えとは重みが違う。

**進行記録は陳腐化を引き起こさない**。[ワークフローモデル](phase2-workflow-model.md)のイベントは要件の内容ではなく、どの生成物も依存しない。

---

## 5. カバレッジ判定

**カバレッジ判定は課題に応答する生成物にのみ適用する**。全Artifactに要求すると、要件セクションに依存しないはずの `research` / `fermi` まで `challenges` 依存になり、型別依存規則と矛盾する。

| 適用する | 適用しない |
|---|---|
| `mini-prfaq` / `prfaq` / `comparison` / `architecture` / `mock` | `research` / `fermi` / `as-is-report` / `slides` |

適用しない型では `covered_challenge_ids` を無視する(保存されていても判定に使わない)。`as-is-report` と `slides` は現状の記述と共有が目的であり、課題への応答ではない。

適用する型は **`covered_challenge_ids: list[str]`** を持つ。生成時点の要件に存在した課題IDのうち、その生成物が扱ったものを記録する。最新要件の `scope: "core"` な課題ID集合との差分に未対応のものがあれば `stale` とする。

- **本文の文字列一致やLLM判定でカバレッジを推定しない**(設計原則に反する)。Skillが保存時に明示的に宣言する
- **既存Artifact(フィールド未設定)の扱い**: 推測によるバックフィルはしない。未設定の生成物はカバレッジ判定を `outdated`(差分確認推奨)とし、`stale` にはしない
