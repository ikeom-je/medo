# フェーズ2 ドメインモデル

案件内容の正本となる要件ドキュメントのスキーマ。索引: [medo-phase2-design.md](medo-phase2-design.md)

**この層が持つのは案件の内容だけ**である。ヒアリングの進行記録(レビュー・反応・チェックポイント)は[ワークフローモデル](phase2-workflow-model.md)が持つ。

---

## 1. 論理連鎖

```
事実調査(出典付き) → 公開情報から見える現状(as-is: public)
                          │
                          │ 認識GAP を契機に実態を掘る(暗黙知の発見)
                          ▼
                    ヒアリング → 現場の実態(as-is: internal)
                          ↕
                    ┌─────┴─────┐  ★往復が暗黙知を引き出す
                    │  仮説のToBe  │  仮のToBeをプローブとして置くと
                    │ (assumed)  │  「それは無理で、実は…」が出てくる
                    └─────┬─────┘  往復のたびに確度が上がる
                          ↓
                    あるべき姿(to-be: confirmed)・成功指標(KPI)の合意
                          ↓
                    目標GAP(状態の乖離) → ボトルネック(真因)
                          ↑ 既往の取り組みと頓挫理由(なぜまだ解決していないか)
                          ↓
                    課題(解くべき問い)+ 仮説(検証すべき前提)
                          ↓        ※制約条件・ステークホルダーの中で解く
                    優先度・効果の比較
```

**AsIsに内部実態が入らないままToBeを確定させると、理想の正論に終わる**。公開情報だけのAsIsからは一般論しか出ない。ただし**内部実態が揃うのを待ってからToBeを書くのではない** — 仮説のToBeをぶつける往復こそが暗黙知を引き出す機構である。

**認識GAPと目標GAPは連鎖上の役割が違う**。認識GAPは実態を発見するための**契機**であり、打ち手のパイプライン(真因→課題→打ち手)に直接流さない。パイプラインに流れるのは、発見された実態から導かれた目標GAPである。

---

## 2. ヒアリングにおける項目の扱い

スキーマが細分化された状態で「空欄を埋める」ことを機械的に追求すると、顧客が答えられない項目を質問し続ける**穴埋め尋問**になり対話が破綻する。顧客はGAPと真因の区別、仮説の検証手順といったオントロジーに沿って話してくれない。

| 分類 | 項目 | ヒアリングでの扱い |
|---|---|---|
| **顧客に直接問う(初期ミニマム)** | `as_is(visibility="internal")`(現状・症状・不満などの**生の声**) / `stakeholders` | 顧客がそのまま答えられる。**ここだけで開始できる** |
| **対話の深化に応じて引き出す** | `constraints` / `stakeholders.pains` | 初回必須にしない。関係が深まってから |
| **合意を取りにいく** | `to_be` / `kpis` / `principles` | ブレストで一緒に言語化する。`to_be` は早い段階から仮説(`assumed`)として置き、往復で確度を上げる |
| **Skillが下書きして確認する** | `gaps` / `bottlenecks` / `challenges` / `hypotheses` | 顧客に直接答えを求めない。対話内容からSkillが `confidence: assumed` で下書きし、「こう捉えて合っていますか」と**ぶつけて確認する** |

**顧客の生の声(症状・不満)は `as_is` と `stakeholders.pains` が受ける**。`challenges` は「解くべき問い」であり、真因分析を経てSkillが整理するもの。生の声をそのまま `challenges` に入れると、真因分析前に構造エラー扱いになる。

### 暗黙知は「問う」だけでは出てこない

暗黙知は直接問われても出てこない。顧客自身が言語化できない場合と、警戒して建前しか答えない場合の両方で対話が止まる。

したがって**Skillが公開情報・技術ナレッジから粗い仮説(Strawman)を先に下書きし、顧客に反論・修正させる**。「ここは実際には手作業で転記されていませんか」と当てて初めて「実は…」と実態が出る。

この手法は実務で **Strawman Proposal** や **Sacrificial Concept** と呼ばれ、学術的には **Provotyping** として研究されている。

- [Sacrificial Concepts](https://medium.com/design-thinking-group/sacrificial-concepts-design-thinking-tool-e00c3c3933c0)
- [Straw Man Proposal](https://en.wikipedia.org/wiki/Straw_man_proposal)
- [Provotyping: deliberate provocations for design research](https://www.researchgate.net/publication/262272464_Provotyping_deliberate_provocations_for_design_research)

**リスクは、顧客が仮説を確定仕様やコミットメントと誤認すること、および初期案への思考固定(アンカリング)である**。Skillの提示方針として次を契約に含める:

- **壊される前提の叩き台であることを宣言してから提示する**(「反論をいただくために置きます」)
- **単一案を正解として置かず、振れ幅のある2〜3案を対比で提示する**。単一案はアンカリングを最も強く招く

---

## 3. ノードとIDの規約

```python
class Node(BaseModel):
    id: str = ""                    # 空なら保存時にcoreが採番
    text: str
    confidence: Confidence = "open" # confirmed | assumed | open
    evidence_refs: list[str] = []   # fact-id / knowledge-id(出典による裏づけ)
```

**ID規約**:

- **プロジェクト内でグローバル一意**。セクション別プレフィックス(`as-` / `tb-` / `kpi-` / `sh-` / `gap-` / `bn-` / `ch-` / `cs-` / `at-` / `hyp-` / `oq-`)
- **採番対象**: IDを持つ全モデル

**採番と検証のシーケンス**(`RequirementsStore.save` 内で実行):

```
1. 直前バージョンを取得(無ければ空として扱う)
2. 入力ドキュメント内のID重複を検証         → 重複はエラー
3. 非空IDが直前バージョンに存在するか検証   → 存在しないIDはエラー
   (ホストLLMが書き写す際の勝手なリナンバリングを機械的に検出する)
4. 空IDに採番(プレフィックス+連番。既発番の最大値+1。削除済みIDは再利用しない)
5. 型付きリンクの参照先が採番後の文書内に存在するか検証 → 不明参照はエラー
6. 保存
```

**リンクは型付きにする**(汎用の `links: list[str]` にしない):

```python
class AsIs(Node):
    visibility: Literal["public", "internal"]      # 既定値なし(必須)
    # public:   公開情報・市場調査で観測できる姿
    # internal: 対話および顧客提供資料から分かる実態
    source_stakeholder_ids: list[str] = []        # 誰の視点に基づく実態か
    reality_checked: bool = False                 # public用: 現場実態と突合済みか

class ToBe(Node):
    scope: Scope = "core"                         # core | secondary | out
    evidenced_by: list[str] = []                  # 確度昇格の契機になったノードID(経緯の記録)

class Gap(Node):
    kind: Literal["perception", "internal_conflict", "goal"] = "goal"
    from_as_is: list[str] = []
    from_to_be: list[str] = []       # goal のみ

class Bottleneck(Node):
    gap_ids: list[str] = []          # kind="goal" の gap のみ参照する
    from_hypothesis: str = ""        # 昇格元の仮説ID

class Challenge(Node):
    scope: Scope = "core"                   # core | secondary | out
    bottleneck_ids: list[str] = []          # 確定した真因
    cause_hypothesis_ids: list[str] = []    # 未検証の真因(検証途上はこちら)
```

**`AsIs.visibility` は既定値を持たない必須項目**とする。既定 `internal` にすると、指定漏れの公開情報まで内部実態として扱われ、認識GAPの検出が壊れる。`as_is` はフェーズ2の新規セクションで既存データが無いため、必須化しても後方互換は損なわれない。

**`AsIs.reality_checked` は「突合したが乖離が無かった」を記録する**。突合の実施を `perception` Gap の存在だけで判定すると、公開情報と実態が一致していた正常なケースで乖離が生まれず Gap も作られないため、永続的に「未突合」と誤検出され続ける。

**`internal` の情報源は対話に限らない**。業務フロー図・運用マニュアル・障害ログ・帳票といった顧客提供の一次資料も実態の情報源になる。むしろ暗黙知は資料の実物を見て初めて言語化されることが多い。出典は `evidence_refs` に `kind: company` のファクト(由来表記に資料名を記載)として紐づける。

**`evidence_refs` と `visibility` の関係は推奨であって強制ではない**。現行 `Fact.kind`(market/policy/trend/company)は**対象領域の分類であって公開性の分類ではない** — `policy`(国策)は公開情報だが `company` は非公開とは限らない。したがって機械的な強制はしない。

### GAPの3種別と下流での役割

| GAP種別 | 意味 | 下流での役割 |
|---|---|---|
| `goal` | あるべき姿 と 現状 の乖離 | `bottleneck` → `challenge` → 打ち手のパイプラインに流す |
| `perception` | 公開情報から見える姿 と 現場実態 の乖離 | **隠れた `AsIs(internal)` を発見・確定するための契機**。パイプラインに直接流さない |
| `internal_conflict` | 立場による実態認識の相違(経営層の見る実態 と 現場の実態) | **どちらの実態を前提にToBeを描くかを合意するための論点**。パイプラインに直接流さない |

**保存時の検証**:

- `kind="perception"` の `from_as_is` は `visibility="public"` と `visibility="internal"` を**それぞれ1件以上**参照する
- `kind="internal_conflict"` の `from_as_is` は `visibility="internal"` を**2件以上**参照し、参照先の `source_stakeholder_ids` が異なる
- `kind="perception"` / `kind="internal_conflict"` の `from_to_be` は空でなければならない
- `Bottleneck.gap_ids` が参照できるのは `kind="goal"` の gap のみ

### スコープ属性

課題とGAPは往復のたびに蓄積するが、**すべてを今回解くわけではない**。スコープ属性が無いと、診断が重要度の低い課題にまで一律にアラートを出し、実務が埋没する。

```python
Scope = Literal["core", "secondary", "out"]
# core:      今回の対象
# secondary: 認識しているが今回は扱わない
# out:       対象外と合意済み
```

**診断は既定で `core` のみを対象にする**([status契約](phase2-status-contract.md))。要求の優先順位付けは上流工程の必須タスクとして標準的に位置づけられている([BABOK Guide](https://www.iiba.org/standards-and-resources/babok-guide/))。

---

## 4. RequirementsDoc

```python
class RequirementsDoc(BaseModel):
    # --- 既存(そのまま維持) ---
    project: str
    version: int
    industry: str
    background: str                  # 自由文の背景(as_is の導入として残す)
    goal: str                        # 一文のゴール(kpis が定量面を担う)
    principles: list[ConfidenceItem]
    functional: list[FunctionalRequirement]
    non_functional: dict[str, str]
    sources: list[str]
    knowledge_backend: Literal["markdown", "sqlite"]

    # --- 型を変更(移行が必要) ---
    challenges: list[Challenge] = []      # ConfidenceItem から Challenge へ
    open_questions: list[OpenQuestion] = []  # list[str] から ID付きへ

    # --- 追加 ---
    as_is: list[AsIs] = []
    to_be: list[ToBe] = []
    kpis: list[Kpi] = []
    stakeholders: list[Stakeholder] = []
    gaps: list[Gap] = []
    bottlenecks: list[Bottleneck] = []
    constraints: list[Node] = []      # 予算・期間・体制・法令・既存システム
    attempts: list[Attempt] = []      # 既往の取り組みと、なぜ解決に至っていないか
    hypotheses: list[Hypothesis] = []
```

**`open_questions` を `list[str]` から ID付きへ変更する**。レビュー所見が未確定事項を参照する必要があるが、文字列のリストでは参照先を指せない。

```python
class OpenQuestion(BaseModel):
    id: str = ""        # 採番プレフィックス oq-
    text: str
    scope: Scope = "core"
```

**`challenges` の移行方針**: `Challenge` は `ConfidenceItem` の上位互換。既存JSONは `id` が無い状態で読めるため、**読み込み時に空IDとして扱い、次回保存時に core が採番する**。この初回採番は意味上の変更として扱わない(陳腐化を引き起こさない)。移行対象の実データは1プロジェクト(medo-ops、課題5件)のみ。

**進行記録は含めない**。レビュー・反応・チェックポイントは要件の版とは独立に記録される([ワークフローモデル](phase2-workflow-model.md))。

---

## 5. KPI・ステークホルダー・既往の取り組み

フェルミ推定は効果の桁感を計算するが、**「どの指標をいくら改善するのか」を結ぶノードが無かった**。

```python
class Kpi(Node):
    name: str
    current_fact_id: str = ""        # 現状値は fact への参照(下記の理由)
    target_value: float | None = None
    target_text: str = ""            # 定性目標(「即時化」「ランクA維持」等)
    unit: str = ""
    to_be_ids: list[str] = []

class Stakeholder(Node):
    role: str = ""
    pains: list[str] = []
    stance: Literal["unknown", "supportive", "neutral", "resistant"] = "unknown"
    is_decision_maker: bool = False   # 公式な承認・決裁の権限を持つか
    influence: Literal["high", "medium", "low"] = "medium"   # 非公式な影響力
    interest: Literal["high", "medium", "low"] = "medium"    # この案件への関心度
    surfaced_by: Literal["stated", "inferred"] = "stated"
```

**現状値を `float` で直接持たず `fact` を参照する**。KPIの現状値は観測された事実であり、設計原則「数値・事実の通り道にLLMを挟まない」の対象。`kind: company` のファクト(ヒアリング由来・URL不要)として保存し参照することで、出典・取得日・stale判定が自動的に効く。`target_value` は観測事実ではなく合意された決定なので数値のまま持ち、`confidence` が確度を表す。

**`influence` と `interest` を決裁権限とは別に持つ**。案件を最も頓挫させるのは「決裁権限はないが拒否権を持つ実力者」であり、公式な決裁権だけでは捕捉できない。この2軸はステークホルダー分析の標準([Power-Interest Grid](https://en.wikipedia.org/wiki/Stakeholder_analysis))に対応する。

**`surfaced_by` は発見経路の記録であり、確認プロセスの実施結果ではない**。「Skillが推定した関係者が1人もいない」ことは「探索しなかった」とも「探索したが追加はいなかった」とも解釈できる。確認プロセスの実施は[ワークフローモデル](phase2-workflow-model.md)の `DiscoveryChecks` が保持する。

### 既往の取り組み(Attempt)

**「なぜ今まで解決に至っていないのか」を保持する**。一度も着手していない課題と、複数回試して頓挫した課題はまったく別物であり、後者には隠れた制約・力学が潜んでいる。

```python
BlockerCategory = Literal[
    "resource",            # 予算・人材・時間の不足
    "politics_incentive",  # 部門間の利害対立・インセンティブ不整合
    "technical",           # 技術的困難・技術負債
    "governance",          # 承認プロセス・規制・コンプライアンス
    "priority",            # 他施策に優先度で負けた・タイミング
]

class Attempt(BaseModel):
    id: str = ""                          # 採番プレフィックス at-
    challenge_ids: list[str] = []         # 既存 Challenge のIDのみ参照可
    gap_ids: list[str] = []               # 既存 Gap のIDのみ参照可
    description: str                      # 何をやったか
    outcome: Literal["not_attempted", "in_progress", "stalled", "failed", "partial", "succeeded"]
    blocker: str = ""                     # なぜ進まなかった/失敗したか
    blocker_category: list[BlockerCategory] = []
    confidence: Confidence = "open"
    evidence_refs: list[str] = []
```

`outcome` が `stalled` / `failed` の `blocker` は、`constraints` と `bottlenecks` の最有力の発見源になる。**`blocker_category` を併記する** — 自由文だけだと表面的な言い訳(「多忙だった」「予算がなかった」)をそのまま記録して完了扱いになり、真因への深掘りが起きない。類型により、Skillが掘る方向を判断できる。

**`not_attempted` を明示的に持つ理由**: 「取り組んでいない」という記録と「まだ聞いていない」という空欄を区別するため。前者は確認済みの事実であり、後者は未確認。

**保存時の検証**: `outcome` が `stalled` / `failed` の場合は `blocker` を必須とする。`challenge_ids` / `gap_ids` は同一ドキュメント内に実在するIDのみ参照可(存在しないIDで未確認警告を消せてしまうことを防ぐ)。

---

## 6. 仮説(Hypothesis)

`confidence` は「今どれだけ確からしいか」、`Hypothesis` は「何を検証すれば確定するか」を持つ。両者は補完関係。

```python
class FermiRef(BaseModel):
    artifact_id: str               # 例: "fermi-v2"
    variable_name: str             # モデル内の assume 変数名

class Hypothesis(BaseModel):
    id: str = ""                   # 採番プレフィックス hyp-
    kind: Literal["cause", "solution", "impact"]
    statement: str
    validation_method: str = ""
    status: Literal["unvalidated", "validating", "validated", "rejected"] = "unvalidated"
    evidence_refs: list[str] = []
    challenge_ids: list[str] = []
    fermi_ref: FermiRef | None = None   # kind="impact" の場合(感度分析の接続点)
```

**未検証の真因は `hypotheses(kind="cause")` に一元管理する**。`bottlenecks` は検証・合意済みの真因のみ(`confidence: confirmed`)を持ち、仮説が検証されたら(`status: validated`)`bottlenecks` に昇格させて `from_hypothesis` に元の仮説IDを記録する。二重管理を避けつつ昇格の経緯が追跡できる。

**`fermi_ref` の検証契約**: 保存時に `artifact_id` が同一プロジェクトに実在し `type == "fermi"` であること、`variable_name` がそのモデルの `variables` に存在することを検証する。検証箇所は Store(Pydantic単体では他Artifactを参照できないため)。
