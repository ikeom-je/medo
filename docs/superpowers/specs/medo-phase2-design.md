# Medo フェーズ2 設計ドキュメント

ステータス: レビュー中(3エージェント相互検証を3ラウンド実施済み。実装計画化の前にユーザー承認が必要)

正本: 本ファイル。全体設計は `medo-design.md` を参照し、本ファイルはフェーズ2の差分を定義する。

---

## 1. 目的とスコープ

フェーズ1は「What/Whyの合意形成」の縦切りを通した。フェーズ2は、その合意形成を**利用者が漏れなく重複なく進められるよう導く**支援に踏み込む。

利用者が求める論理連鎖:

```
事実調査(出典付き) → 公開情報から見える現状(as-is: public)
                          │
                          │ 認識GAP を契機に実態を掘る(暗黙知の発見)
                          ▼
                    ヒアリング → 現場の実態(as-is: internal)
                          ↓
                    あるべき姿(to-be)・成功指標(KPI)の言語化
                          ↓
                    目標GAP(状態の乖離) → ボトルネック(真因)
                          ↑ 既往の取り組みと頓挫理由(なぜまだ解決していないか)
                          ↓
                    課題(解くべき問い)+ 仮説(検証すべき前提)
                          ↓        ※制約条件・ステークホルダーの中で解く
                    優先度・効果の比較
                          ↓
                    共感できるドキュメント → スライド
```

**認識GAPと目標GAPは連鎖上の役割が違う**。認識GAPは実態を発見するための**契機**であり、打ち手のパイプライン(真因→課題→打ち手)に直接流さない。パイプラインに流れるのは、発見された実態から導かれた目標GAPである(3.1参照)。

**実態のAsIsを可視化せずにToBeを描くと、理想の正論に終わる**。認識GAPと「なぜ解決していないか」の2つが、この失敗を防ぐ要になる(判断4)。

**medoの位置づけ**: 利用者を導く支援ツールであり、判断を代行しない。フレームワークをパターンとして整理し、MECE(漏れなく重複なく)なヒアリングを支える。

---

## 2. 設計判断

### 判断1: フレームワークに基づく固定スキーマを持つ

汎用ノード+種別タグではなく、フレームワークに基づく**named field**として持つ。

**理由**: 支援ツールの役割は利用者を導くこと。項目が定義されていなければ「何が漏れているか」を機械的に指摘できず、MECEを担保できない。

### 判断2: 順序は固定しない

実案件は典型パターンに従わない。理想像から語り始めることも、特定の制約から入ることも、症状だけが見えている状態から始まることもある。

- **CLI(決定論)**: 構造の充足状況(空のセクション・assumed/openのみの項目・繋がっていないリンク)を返す
- **Skill(生成的)**: それを見て「次に何をどう問うか」を決める

### 判断3: 顧客に問う項目と、Skillが下書きする項目を分ける

**相互レビュー(agy)の指摘を採用した最重要の判断**。スキーマが細分化された状態で「空欄を埋める」ことを機械的に追求すると、顧客が答えられない項目を質問し続ける**穴埋め尋問**になり対話が破綻する。

顧客はGAPと真因の区別、仮説の検証手順といったオントロジーに沿って話してくれない。

| 分類 | 項目 | ヒアリングでの扱い |
|---|---|---|
| **顧客に直接問う(初期ミニマム)** | `as_is`(現状・症状・不満などの**生の声**) / `stakeholders` | 顧客がそのまま答えられる。**ここだけで開始できる** |
| **対話の深化に応じて引き出す** | `constraints` / `stakeholders.pains` | 初回必須にしない。関係が深まってから |
| **合意を取りにいく** | `to_be` / `kpis` / `principles` | ブレストで一緒に言語化する |
| **Skillが下書きして確認する** | `gaps` / `bottlenecks` / `challenges` / `hypotheses` | 顧客に直接答えを求めない。対話内容からSkillが `confidence: assumed` で下書きし、「こう捉えて合っていますか」と**ぶつけて確認する** |

**重要**: 顧客の生の声(症状・不満)は `as_is` と `stakeholders.pains` が受ける。`challenges` は「解くべき問い」であり、真因分析を経てSkillが整理するもの。**生の声をそのまま `challenges` に入れない**(相互レビューで、生の声を課題として扱うと真因分析前に構造エラー扱いになると指摘された)。

初回ヒアリングは `as_is` + 生の声だけで成立し、残りは対話の深化とSkillの下書きで埋まる。

### 判断4: 実態のAsIsを可視化してからToBeへ進む

**AsIsには非公開情報と暗黙知が含まれる。これを可視化せずにToBeを描くと、理想の正論に終わる。** 現実のAsIsを共有・共感して初めて、ToBeとステップbyステップのアクション(実現のための戦略と設計)を検討できる。

この失敗を防ぐため、ヒアリングに以下3つの確認プロセスを**Skillの契約として義務付ける**。実施結果は `process_checks`(3.5)に記録し、`medo status` が未実施を検出する。

**前提となる姿勢: 暗黙知は「問う」だけでは出てこない**

相互レビュー(agy)の指摘により明文化する。暗黙知は直接問われても出てこない。顧客自身が言語化できない場合と、警戒して建前しか答えない場合の両方で対話が止まる。

したがって3プロセスすべてに共通して、**Skillが公開情報・技術ナレッジから粗い仮説(Strawman)を先に下書きし、顧客に反論・修正させる**アプローチを取る。「ここは実際には手作業で転記されていませんか」と当てて初めて「実は…」と実態が出る。これは判断3の「Skillが下書きして確認する」を `as_is` にも適用することを意味する。

#### プロセス1: 公開情報から見える姿を、現場実態と突き合わせる

市場調査・公開情報で観測できる姿(`visibility: public`)と、ヒアリングでしか分からない実態(`visibility: internal`)を両方記録し、乖離を `Gap(kind="perception")` として保持する。

**確認の方向は「public起点」とする**(相互レビューでCodex・agyが独立に指摘)。内部実態のすべてに公開情報の対応物があるわけではない — 伝票転記の手間や例外処理にIR開示は存在しない。全 `internal` に `public` の対応物を求めると偽陽性が大量発生し、警告が形骸化する。

したがって検証は逆向きに行う: **調査・登録した `public` の記述それぞれについて、現場実態との突合が行われたか**を確認する。

**組織防衛を招かない問い方をする**(agy指摘。最重要):

標榜していること(公約)と現場の実態の乖離を不用意に突くと、組織は自己防衛のために隠蔽・反発に走り対話が閉じる(Argyrisの組織防衛論)。「対外的にはこう見えていますが実態は」という問いは告発・尋問と受け取られやすい。

**非難を伴わない協調的探索の問いに変換する**ことをSkill契約とする:

| 避ける問い方 | 用いる問い方 |
|---|---|
| 「対外的にはこう見えていますが、実態は違いますよね」 | 「目標達成に向けて、現場で直面している想定外の制約は何でしょうか」 |
| 「公約と実態が乖離していませんか」 | 「外部環境の変化に対して、現場の仕組みの追随はどこまで進んでいますか」 |

#### プロセス2: なぜ今まで解決に至っていないのかを問う

課題に対して**既に打たれた施策とその結果**(`attempts`)を確認する。一度も着手していない課題と、複数回試して頓挫した課題はまったく別物であり、後者には隠れた制約・力学が潜んでいる。

`blocker`(頓挫理由)は自由文だけでなく**類型を併記する**(agy指摘)。自由文のみだと表面的な言い訳(「多忙だった」「予算がなかった」)をそのまま記録して完了扱いになり、真因への深掘りが起きない。類型により、Skillがどの方向に掘るかを判断できる(`politics_incentive` ならステークホルダーの利害、`technical` ならアーキテクチャ制約)。

#### プロセス3: 隠れたステークホルダーの存在を問う

顧客が最初に挙げるステークホルダーは、たいてい当事者と直属の関係者に限られる。**承認が必要な人、影響を受ける現場、反対しうる部門**は明示的に問わないと出てこない。

特に案件を頓挫させるのは「決裁権限はないが拒否権を持つ実力者」である(agy指摘)。公式な決裁権と非公式な影響力は別物として捉える必要があるため、`influence`(影響力)と `interest`(関心度)を決裁権限とは別に持つ。

### 判断5: 要素間のリンクは任意にする

「すべての課題はGAPに紐づく」といった強制はしない。**繋がっていないこと自体を情報として扱う**。

**未接続はエラーにしない**。CLIは「充足していない状態」として報告するだけで、保存を拒否しない。

### 判断6: 解像度は confidence が制御する

| confidence | 期待する解像度 |
|---|---|
| `confirmed`(利用者が明言 / 合意済み) | 高。判断に使える |
| `assumed` / `open` | 低くてよい。空欄のままでよい |

**空欄はペナルティではなく「まだ聞けていない/まだ下書きしていない」という情報**。

### 判断7: GAP(現象)とボトルネック(真因)を分離する

現象の差分をそのまま課題と呼ぶと対症療法しか出ない(agy指摘)。

```
to_be − as_is = gap(現象) → bottleneck(真因) → challenge(解くべき問い)
```

### 判断8: 未検証の真因は hypotheses に一元管理する

`bottlenecks` と `hypotheses(kind="cause")` の責務重複を解消する。

- **`bottlenecks`**: 検証・合意済みの真因のみ(`confidence: confirmed`)
- **`hypotheses(kind="cause")`**: 未検証・要検証の真因

仮説が検証されたら(`status: validated`)`bottlenecks` に昇格させ、`from_hypothesis` に元の仮説IDを記録する。

---

## 3. スキーマ設計

既存フィールドは維持し、追加は原則として既定値ありの additive change とする。**唯一の例外は `AsIs.visibility`**(既定値を持たせると認識GAPの検出が壊れるため。3.1参照)。`as_is` はフェーズ2の新規セクションであり既存データが存在しないため、必須化しても後方互換は損なわれない。

### 3.1 Node と ID の規約

```python
class Node(BaseModel):
    id: str = ""                    # 空なら保存時にcoreが採番
    text: str
    confidence: Confidence = "open"
    evidence_refs: list[str] = []   # fact-id / knowledge-id(出典による裏づけ)
```

**ID規約**:

- **プロジェクト内でグローバル一意**。セクション別プレフィックス(`as-` / `tb-` / `kpi-` / `sh-` / `gap-` / `bn-` / `ch-` / `cs-` / `at-` / `hyp-`)
- **採番対象**: Node系全セクション + `Attempt` + `Hypothesis`(IDを持つ全モデル)

**採番と検証のシーケンス**(Codex指摘により明文化。`RequirementsStore.save` 内で実行):

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

class Gap(Node):
    kind: Literal["perception", "internal_conflict", "goal"] = "goal"
    # perception:        公開情報から見える姿 と 現場実態 の乖離(実態発見の契機)
    # internal_conflict: 立場による実態認識の相違(経営層の見る実態 と 現場の実態)
    # goal:              あるべき姿 と 現状 の乖離(打ち手の対象)
    from_as_is: list[str] = []
    from_to_be: list[str] = []       # goal のみ

class Bottleneck(Node):
    gap_ids: list[str] = []          # kind="goal" の gap のみ参照する
    from_hypothesis: str = ""        # 昇格元の仮説ID(判断8)

class Challenge(Node):
    bottleneck_ids: list[str] = []          # 確定した真因
    cause_hypothesis_ids: list[str] = []    # 未検証の真因(検証途上はこちら)
```

**`Gap.kind` は2種類のGAPを区別する**。従来は「あるべき姿 − 現状」の目標GAPしか扱えなかったが、**「公開情報から見える姿 − 現場実態」の認識GAP**を保持しないと、暗黙知が可視化されないままToBeが理想の正論に終わる(判断4 プロセス1)。

**2つのGAPは下流での役割が異なる**(agy指摘により明文化)。目標GAPの解消は「打ち手の導入」だが、認識GAPの解消は「実態の直視」であり、解くべき問いの性質が違う。同じパイプラインに流すと真因分析と打ち手選定で議論が混濁する。

| GAP種別 | 下流での役割 |
|---|---|
| `goal` | `bottleneck` → `challenge` → 打ち手のパイプラインに流す |
| `perception` | **隠れた `AsIs(internal)` を発見・確定するための契機**。直接パイプラインに流さない。乖離そのものが解くべき問題なら、判明した実態を `AsIs(internal)` として記録し、そこから目標GAPを導出する |
| `internal_conflict` | **どちらの実態を前提にToBeを描くかを合意するための論点**。直接パイプラインに流さない |

**`internal_conflict` は agy指摘により追加**。`source_stakeholder_ids` で視点は分けられるが、「経営層が認識する実態」と「現場の実態」が衝突していること自体を表現する手段が無かった。この衝突を可視化しないまま先へ進むと、ToBe策定でどちらの実態を前提にするか迷走する。

**保存時の検証**(Codex指摘により明文化):

- `kind="perception"` の `from_as_is` は `visibility="public"` と `visibility="internal"` を**それぞれ1件以上**参照する(片側だけでは対応関係が成立しないため)
- `kind="internal_conflict"` の `from_as_is` は `visibility="internal"` を**2件以上**参照し、参照先の `source_stakeholder_ids` が異なる
- `kind="perception"` / `kind="internal_conflict"` の `from_to_be` は空でなければならない
- `Bottleneck.gap_ids` が参照できるのは `kind="goal"` の gap のみ

**`AsIs.visibility` は既定値を持たない必須項目**とする(Codex指摘)。既定 `internal` にすると、指定漏れの公開情報まで内部実態として扱われ、認識GAPの検出が壊れる。

**`AsIs.source_stakeholder_ids` は誰の視点かを保持する**(agy指摘)。経営層の考える「実態」と現場オペレーターの「実態」は乖離する。単一の客観事実として記録すると、声の大きいステークホルダーの主観が実態として固定化される。

**`AsIs.reality_checked` は「突合したが乖離が無かった」を記録する**(Codex・agyが独立に指摘)。突合の実施を `perception` Gap の存在だけで判定すると、**公開情報と実態が一致していた正常なケース**で乖離が生まれず Gap も作られないため、永続的に「未突合」と誤検出され続ける。`not_attempted`(3.4)と同じ「確認済みの不在」を表す記録である。

**`internal` の情報源は対話に限らない**(agy指摘)。業務フロー図・運用マニュアル・障害ログ・帳票といった顧客提供の一次資料も実態の情報源になる。むしろ暗黙知は資料の実物を見て初めて言語化されることが多い。出典は `evidence_refs` に `kind: company` のファクト(由来表記に資料名を記載)として紐づける。

**`evidence_refs` と `visibility` の関係は推奨であって強制ではない**(Codex指摘により明確化)。現行 `Fact.kind`(market/policy/trend/company)は**対象領域の分類であって公開性の分類ではない** — `policy`(国策)は公開情報だが、`company` は非公開とは限らない。したがって「publicなら market/trend fact」という機械的な強制はしない。出典を伴うことは推奨するが、`visibility` の正しさは出典からは保証されない。

**`Challenge.cause_hypothesis_ids` は相互レビュー(agy)の指摘により追加**。真因がまだ仮説段階にある健全な検証途上で、CLIが「未リンク」を警告し続けてしまう問題を防ぐ。未リンク警告は**両方が空のときのみ**出す。

### 3.2 RequirementsDoc の拡張

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
    open_questions: list[str]
    sources: list[str]
    knowledge_backend: Literal["markdown", "sqlite"]

    # --- 型を変更(移行が必要) ---
    challenges: list[Challenge] = []  # ConfidenceItem から Challenge へ

    # --- 追加 ---
    as_is: list[AsIs] = []            # visibility で public / internal を区別
    to_be: list[Node] = []
    kpis: list[Kpi] = []
    stakeholders: list[Stakeholder] = []
    gaps: list[Gap] = []              # kind で perception / goal を区別
    bottlenecks: list[Bottleneck] = []
    constraints: list[Node] = []      # 予算・期間・体制・法令・既存システム
    attempts: list[Attempt] = []      # 既往の取り組みと、なぜ解決に至っていないか
    hypotheses: list[Hypothesis] = []
    process_checks: ProcessChecks = ProcessChecks()   # 判断4の3確認プロセスの実施結果
```

**`challenges` の移行方針**: `Challenge` は `ConfidenceItem` の上位互換。既存JSONは `id` が無い状態で読めるため、**読み込み時に空IDとして扱い、次回保存時に core が採番する**。この初回採番は意味上の変更として扱わない(陳腐化を引き起こさない)。移行対象の実データは1プロジェクト(medo-ops、課題5件)のみ。

### 3.3 KPI とステークホルダー

フェルミ推定は効果の桁感を計算するが、**「どの指標をいくら改善するのか」を結ぶノードが無かった**(agy指摘)。

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
    is_decision_maker: bool = False       # 公式な承認・決裁の権限を持つか
    influence: Literal["high", "medium", "low"] = "medium"   # 非公式な影響力
    interest: Literal["high", "medium", "low"] = "medium"    # この案件への関心度
    surfaced_by: Literal["stated", "inferred"] = "stated"
    # stated:   顧客が自ら挙げた
    # inferred: Skillが推定して確認を求めた(隠れたステークホルダーの発見)
```

**`influence` と `interest` を決裁権限とは別に持つ**(agy指摘)。案件を最も頓挫させるのは「決裁権限はないが拒否権を持つ実力者」や「現場でサボタージュする利用部門長」であり、公式な決裁権(`is_decision_maker`)だけでは捕捉できない。この2軸はステークホルダー分析の標準(Power-Interest Matrix)に対応し、エンゲージメント方針の決定に使う。

**`surfaced_by` は発見経路の記録であり、確認プロセスの実施結果ではない**(Codex指摘により役割を限定)。「Skillが推定した関係者が1人もいない」ことは「探索しなかった」とも「探索したが追加はいなかった」とも解釈でき、両者を区別できない。確認プロセスの実施は `process_checks`(3.5)が保持する。

### 3.4 既往の取り組み(Attempt)

**「なぜ今まで解決に至っていないのか」を保持する**(判断4 プロセス2。レビュー指摘により追加)。一度も着手していない課題と、複数回試して頓挫した課題はまったく別物であり、後者には隠れた制約・力学が潜んでいる。

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

`outcome` が `stalled` / `failed` の `blocker` は、`constraints` と `bottlenecks` の最有力の発見源になる。Skillは blocker から真因仮説を下書きして確認する。

**`blocker_category` を併記する**(agy指摘)。自由文だけだと表面的な言い訳(「多忙だった」「予算がなかった」)をそのまま記録して完了扱いになり、真因への深掘りトリガーが働かない。類型により、Skillが掘る方向を判断できる — `politics_incentive` ならステークホルダーの利害、`technical` ならアーキテクチャ制約へ質問を連動させる。

**`not_attempted` を明示的に持つ理由**: 「取り組んでいない」という記録と「まだ聞いていない」という空欄を区別するため。前者は確認済みの事実であり、後者は未確認。

**保存時の検証**(Codex指摘): `outcome` が `stalled` / `failed` の場合は `blocker` を必須とする。`challenge_ids` / `gap_ids` は同一ドキュメント内に実在するIDのみ参照可(存在しないIDで未確認警告を消せてしまうことを防ぐ)。

### 3.5 確認プロセスの実施記録(ProcessChecks)

**「未確認」と「確認したが該当なし」を区別する**(Codex・agyが独立に指摘)。データの形から確認プロセスの実施を推測すると誤判定になる — 推定した関係者を1件置くだけで警告が消え、逆に質問して「他にいない」と確認した正常なケースでは永続的に警告され続ける。

```python
CheckState = Literal["unverified", "confirmed_none", "identified"]
# unverified:     まだ確認していない
# confirmed_none: 確認した結果、該当なし(乖離なし / 過去の取り組みなし / 追加の関係者なし)
# identified:     確認して該当があった(対応するレコードが存在する)

class ProcessChecks(BaseModel):
    reality_gap: CheckState = "unverified"          # プロセス1: 公開情報と現場実態の突合
    past_attempts: CheckState = "unverified"        # プロセス2: 既往の取り組みの確認
    hidden_stakeholders: CheckState = "unverified"  # プロセス3: 隠れた関係者の探索
    decision_maker: CheckState = "unverified"       # プロセス3: 決裁者の特定
```

`RequirementsDoc.process_checks` として持つ。

**各 CheckState に対応するレコードを明文化する**(Codex指摘。これが無いと `identified` の整合を機械判定できない):

| 項目 | `identified` が意味する対応レコード |
|---|---|
| `reality_gap` | `Gap(kind="perception")` が1件以上 |
| `past_attempts` | `Attempt` が1件以上(`outcome` は問わない) |
| `hidden_stakeholders` | `Stakeholder(surfaced_by="inferred")` が1件以上 |
| `decision_maker` | `Stakeholder(is_decision_maker=True)` が1件以上 |

**不整合の判定は双方向で行う**: `identified` なのに対応レコードが0件の場合と、`confirmed_none` なのに対応レコードが存在する場合の**両方**を `inconsistent_checks` で報告する。

**`ProcessChecks` はヒアリングの進行記録であって、要件の内容ではない**。したがって生成物の依存セクション(5.3)には含めず、その変更は生成物を陳腐化させない(5.2参照)。

**現状値を `float` で直接持たず `fact` を参照する理由**: KPIの現状値は観測された事実であり、設計原則「数値・事実の通り道にLLMを挟まない」の対象。`kind: company` のファクト(ヒアリング由来・URL不要)として保存し、`current_fact_id` で参照する。これにより出典・取得日・stale判定が自動的に効く。

**`target_value` は数値のまま**保持する。目標は観測事実ではなく合意された決定であり、`confidence` が確度を表す。数値化できない目標は `target_text` を使う(相互レビューで、初期段階の定性目標が扱えず入力が止まるリスクを指摘された)。

`stakeholders.pains` は Section 6 の共感要素②の入力になる。**保存先は要件ドキュメント**とする(顧客個人名ではなく役割と痛みを記録する運用とし、個人特定情報は書かない)。

### 3.6 仮説(Hypothesis)

`confidence` は「今どれだけ確からしいか」、`Hypothesis` は「何を検証すれば確定するか」を持つ。

```python
class FermiRef(BaseModel):
    artifact_id: str               # 例: "fermi-v2"
    variable_name: str             # モデル内の assume 変数名

class Hypothesis(BaseModel):
    id: str = ""
    kind: Literal["cause", "solution", "impact"]
    statement: str
    validation_method: str = ""
    status: Literal["unvalidated", "validating", "validated", "rejected"] = "unvalidated"
    evidence_refs: list[str] = []
    challenge_ids: list[str] = []
    fermi_ref: FermiRef | None = None   # kind="impact" の場合(感度分析の接続点)
```

**`fermi_ref` の検証契約**(Codex指摘により明文化): 保存時に `artifact_id` が同一プロジェクトに実在し `type == "fermi"` であること、`variable_name` がそのモデルの `variables` に存在することを検証する。検証箇所は Store(Pydantic単体では他Artifactを参照できないため)。

---

## 4. 充足状況の可視化(MECEの担保)

`medo status` を拡張し、**漏れ**を決定論的に返す。**未接続はエラーではなく報告**(判断5)。

```json
{
  "structure": {
    "as_is":        {"count": 3, "confirmed": 2, "empty": false,
                     "public": 1, "internal": 2},
    "to_be":        {"count": 0, "confirmed": 0, "empty": true},
    "kpis":         {"count": 0, "confirmed": 0, "empty": true},
    "stakeholders": {"count": 2, "confirmed": 2, "empty": false},
    "gaps":         {"count": 0, "confirmed": 0, "empty": true,
                     "perception": 0, "goal": 0},
    "bottlenecks":  {"count": 0, "confirmed": 0, "empty": true},
    "constraints":  {"count": 1, "confirmed": 1, "empty": false},
    "attempts":     {"count": 0, "confirmed": 0, "empty": true},
    "challenges":   {"count": 5, "confirmed": 4, "empty": false}
  },
  "unlinked": {
    "challenges_without_cause": ["ch-2"],
    "gaps_without_bottleneck": [],
    "to_be_without_kpi": ["tb-1"],
    "hypotheses_unvalidated": ["hyp-1", "hyp-3"]
  },
  "process_checks": {
    "reality_gap": "unverified",
    "past_attempts": "identified",
    "hidden_stakeholders": "confirmed_none",
    "decision_maker": "unverified"
  },
  "unverified_process": {
    "not_run": ["reality_gap", "decision_maker"],
    "inconsistent_checks": []
  },
  "coverage_gaps": {
    "public_as_is_without_verification": ["as-1"],
    "challenges_without_attempt": ["ch-1", "ch-4"]
  }
}
```

`challenges_without_cause` は `bottleneck_ids` と `cause_hypothesis_ids` の**両方が空**の課題のみを列挙する(3.1参照)。

### 2種類の診断を分ける

いずれも**「漏れの指摘」であって強制ではない**(判断5と同じく、未実施でも保存は拒否しない)。ただし**判定の根拠が異なるため、別のブロックとして返す**(Codex指摘。当初案は両者を同じ `unverified_process` に混在させ、「データ形状から推測しない」という自らの原則と衝突していた)。

| ブロック | 問い | 判定の根拠 |
|---|---|---|
| `unverified_process` | **プロセスを実施したか** | `process_checks`(3.5)のみ。データ形状から推測しない |
| `coverage_gaps` | **個々の対象が処理されているか** | データ形状(レコードの有無)から機械的に導く |

#### `unverified_process`

| キー | 意味 |
|---|---|
| `not_run` | `process_checks` が `unverified` のままの項目 |
| `inconsistent_checks` | `identified` なのに対応レコードが無い、または `confirmed_none` なのに対応レコードが存在するもの(3.5の対応表で判定) |

**「推定した関係者が1件もない」ことは「探索しなかった」とも「探索したが追加はいなかった」とも読める**。この区別はデータ形状からは導けないため、`process_checks` を正とする。

#### `coverage_gaps`

| キー | 意味 | 対応するプロセス |
|---|---|---|
| `public_as_is_without_verification` | 登録済みの `public` な現状のうち、`reality_checked` が偽で、かつその `public` を参照する有効な `perception` Gap も無いもの | プロセス1 |
| `challenges_without_attempt` | 既往の取り組みが1件も紐づいていない課題。`outcome: not_attempted` の記録があれば確認済みとして除外する | プロセス2 |

**プロセス1の検証は `public` 起点で行う**(Codex・agyが独立に指摘した最重要の訂正)。当初案は「`internal` に対応する `public` が無いもの」を検出していたが、これは成立しない:

- 内部実態の大多数には対応する公開情報が存在しない(伝票転記の手間や例外処理にIR開示はない)ため、偽陽性が大量発生して警告が形骸化する
- `Gap.from_as_is` は単なるIDリストであり、「対になる」という対応関係を機械判定できない

したがって方向を逆転し、**調査・登録した公開情報それぞれについて、現場実態と突き合わせたか**を検出する。対応関係は「その `public` ノードを `from_as_is` に含み、かつ `internal` ノードも含む有効な `perception` Gap が存在するか」で一意に判定できる(3.1の保存時検証により保証される)。

**突合したが乖離が無かった場合は `AsIs.reality_checked = True` で記録する**(Codex・agyが独立に指摘)。これが無いと、公開情報と実態が一致していた正常なケースで Gap が生まれず、永続的に未突合と誤検出され続ける。

**重複(MECEのE)の検知はフェーズ2後半**とし、`knowledge-digest` と同じLLM注入方式(fake generate でテスト可能)で**提案専用機能**として実装する。決定論では意味的重複を判定できないため、検出は提案に留め、統合の判断は利用者が行う。

---

## 5. 陳腐化の粒度

### 5.1 決定: セクション単位 + カバレッジ判定 + 2段階の重大度

実データ(medo-ops の v1→v2: 課題1件追加・open_question1件解決)で4パターンを比較した結果:

| 粒度 | 判定結果 | 評価 |
|---|---|---|
| 文書全体(フェーズ1現状) | 3件すべてstale | fermi-v1 は要件に依存しないのに誤検出 |
| **セクション単位** | 2件stale | 誤検出を解消。**採用** |
| ノード単位(依存のみ) | **0件stale** | 「課題の追加」を検出できず取りこぼす |
| ノード単位+カバレッジ | 2件stale | 正確だが安定IDの全面移行が必要 |

**ノード単位の依存追跡だけでは不十分**。追加は既存ノードを変更しないため依存グラフでは何も壊れないが、実際には「打ち手が全課題をカバーしていない」状態になる。

### 5.2 変更の種類による2段階判定

軽微な文言修正で下流の全生成物が連鎖的にstale化すると、実務で再生成ループに陥る(agy指摘)。判定は決定論で行える。**全フィールド型について定義する**(Codex指摘により非Nodeフィールドも網羅):

| 対象 | `stale`(要再生成) | `outdated`(差分確認推奨) |
|---|---|---|
| Node系(as_is/to_be/gaps/bottlenecks/constraints/challenges/stakeholders) | 追加・削除、`confidence` 変更、リンク変更、`evidence_refs` 変更、`AsIs.visibility` / `Gap.kind` の変更 | `text` のみの変更 |
| `Stakeholder` | 上記 + `is_decision_maker` / `stance` / `influence` / `interest` / `surfaced_by` の変更 | `role` / `pains` の変更 |
| `Attempt` | 追加・削除、`outcome` / `blocker` / `blocker_category` / `challenge_ids` / `gap_ids` / `confidence` / `evidence_refs` の変更 | `description` のみの変更 |
| `ProcessChecks` | — | — (下記の理由により陳腐化の対象外) |

**`ProcessChecks` は陳腐化を引き起こさない**(Codex指摘により訂正)。これはヒアリングの進行記録であって要件の内容ではなく、どの生成物も依存しない(5.3の依存表に含まれない)。「ステークホルダーの探索を実施した」という記録が `unverified` から `identified` に変わっても、PRFAQの本文は変わらない。当初案は表の網羅性を優先して `stale` に分類していたが、依存する生成物が存在しない以上その分類は意味を持たない。
| `Kpi` | 追加・削除、`current_fact_id` / `target_value` / `target_text` / `unit` / `to_be_ids` の変更 | `name` のみの変更 |
| `Hypothesis` | 追加・削除、`status` / `fermi_ref` / `challenge_ids` の変更 | `statement` / `validation_method` の変更 |
| `principles` / `functional`(ConfidenceItem) | 追加・削除、`confidence` 変更 | `text` のみの変更 |
| `non_functional`(dict) | キーの追加・削除、値の変更(数値制約のため) | — |
| `open_questions`(list[str]) | 追加・削除 | — |
| `goal`(str) | — | 変更 |
| `background` / `industry` / `sources` | — | 変更 |

`medo status` は両方を返し、`next_step` は `stale` のみを再生成対象とする。

**`Attempt.blocker` を `stale` 側に置く理由**(Codex指摘による訂正): 頓挫理由は「なぜ今まで解決していないか」の核心であり、PRFAQ とスライド章3の記述を実質的に変える。`description`(何をやったか)の言い換えとは重みが違うため、`outdated` では弱すぎる。

### 5.3 生成物の型ごとの依存セクション

**全ArtifactTypeを網羅する**。生成物側の宣言は不要で、型ごとの固定ルールとして core が持つ。

| 生成物type | 依存セクション | 親への依存 |
|---|---|---|
| `fermi` | なし(facts と assume のみ) | — |
| `mini-prfaq` | `goal` / `challenges` / `principles` / `constraints` / `to_be` / `kpis` | — |
| `prfaq` | 上記 + `as_is` / `gaps` / `bottlenecks` / `hypotheses` / `attempts` / `stakeholders` | `grown_from`(候補選択の来歴。伝播対象外) |
| `comparison` | `challenges` / `principles` / `constraints` / `kpis` | — |
| `slides` | `open_questions`(親が依存しない範囲のみ) | **`derived_from` の親に依存し、staleを継承する** |
| `architecture` | `functional` / `non_functional` / `constraints` | — |
| `mock` | `functional` / `constraints` | — |

**`slides` の依存を明確化**(Codex指摘。旧案は「要件への直接依存は持たない」としながら§7で `as_is`・`kpis`・`gaps` 等を直接入力にしており矛盾していた)。`slides` が描画する `as_is` / `to_be` / `kpis` / `gaps` / `bottlenecks` / `hypotheses` は**すべて親 `prfaq` の依存に含まれる**ため、親からの伝播で捕捉できる。親が依存しない `open_questions` のみ直接依存として持つ。

**比較の基準**: 直前バージョンではなく、**`artifact.requirements_version` の文書と最新版**を比較する(`RequirementsStore.get(project, version)` で任意版を取得できるため実装可能)。

### 5.4 カバレッジ判定

`Artifact` に **`covered_challenge_ids: list[str]`** を追加する。生成時点の要件に存在した課題IDのうち、その生成物が扱ったものを記録する。最新要件の課題ID集合との差分に未対応のものがあれば `stale` とする。

- **本文の文字列一致やLLM判定でカバレッジを推定しない**(設計原則に反するため)。Skillが保存時に明示的に宣言する
- **既存Artifact(フィールド未設定)の扱い**: 推測によるバックフィルはしない。未設定の生成物はカバレッジ判定を `outdated`(差分確認推奨)とし、`stale` にはしない。再生成時に宣言されれば以降は正確に判定される

### 5.5 生成物の依存グラフと stale 伝播

**2つの来歴概念を明確に分ける**(Codex指摘):

| フィールド | 意味 | 対象 | stale伝播 |
|---|---|---|---|
| `grown_from` | **候補選択の来歴**(どの候補セットのどの打ち手を選んだか) | `prfaq`(既存・変更なし) | しない |
| `derived_from` | **内容依存の親**(同じ論理の別表現) | `slides`(必須) | **する** |

```python
derived_from: str | None = None   # 親artifact ID(例: "prfaq-v3")
```

**親typeの許容表**(「通常はprfaq」ではなく必須契約として定義):

| 子type | 許容する親type |
|---|---|
| `slides` | `prfaq` |

(将来の派生生成物を追加する際は本表を拡張する)

**実装契約**:

- `ArtifactStore.save` で以下を検証する(Pydantic単体ではStoreを参照できないため検証箇所はStore):
  - `derived_from` の親が同一プロジェクトに実在し、上表の許容typeであること
  - `grown_from.artifact` が実在し、`grown_from.option` がその候補セットの `options` に存在すること
- `status` は**全Artifactを `id -> Artifact` で保持して親を再帰評価**してから、表示用に型ごと最新版へ射影する(現行の `latest_by_type` は非最新版を捨てるため、親が旧版のPRFAQだと解決できない)
- 親の欠落・循環参照は例外にせず、**理由付きで stale** とする
- CLIに `--derived-from` を追加する

---

## 6. 「共感できるドキュメント」の定義

Codex と agy が**独立に**「論理の一貫性は必要条件だが十分条件ではない」と指摘した(確度が高い)。以下の4要素として定義する。

| 要素 | 内容 | 検証方法 |
|---|---|---|
| ①**実態の共有** | 外部から見える姿ではなく**内部の実態**が言語化され、なぜ今まで解決していないかが共有されている | 半自動(`unverified_process` が確認プロセスの未実施を検出) |
| ②論理の一貫性 | as-is → to-be/KPI → gap → 真因 → 課題 → 打ち手 が繋がっている | **自動**(構造の充足とリンクで判定可能。ただし未接続はエラーにせず報告のみ) |
| ③読み手の痛みとBefore/After | `stakeholders.pains` に紐づく具体的な痛み、変化後の体験 | 人間評価(スキーマが入力を保証) |
| ④トレードオフの誠実な開示 | 不確実性・リスク・**採らなかった選択肢とその理由** | 人間評価(`hypotheses` の未検証項目 + `rejected_options`) |

**①を先頭に置く**(レビュー指摘により追加)。実態が共有されないまま論理だけを整えても、受け手には「理想の正論」としか映らず共感は生まれない。共感の起点は論理ではなく、現実の直視である。

### 見送った案の理由を保持する

現状 `prfaq` は採択案のみを育成し、**却下案の見送り理由が失われる**。意思決定者の納得感はここで大きく変わる。

```python
class RejectedOption(BaseModel):
    name: str
    reason: str               # なぜ見送ったか
    accepted_risk: str = ""   # 見送りによって受け入れたリスク

# Artifact に追加
rejected_options: list[RejectedOption] = []
```

**記録するタイミング**(agy指摘により訂正): 見送りの判断は打ち手比較の段階で起きるため、`mini-prfaq` と `comparison` で記録できるようにし、`prfaq` がそれを引き継ぐ。旧案は `prfaq` のみとしていたが、それではスライド4(打ち手比較)に反映できなかった。

これはmedo自身の表現の分担(コードコメント=Why not)と同じ思想である。

---

## 7. スライド生成の設計

**PRFAQの長文をそのままMarpに分割すると「文字だらけの箇条書き」になり、最も共感されない形式になる**(agy指摘)。`make-slides` は要約ではなく、**定型パターンの構造化テンプレート**として設計する。

**7章構成**とする。1章=1枚に固定せず、**全体で10枚前後の展開を許容する**(agy指摘。特に章5は情報密度が高くMarpの1枚に収めると視認性が落ちる)。

| # | 章 | 内容 | 主な入力 |
|---|---|---|---|
| 1 | SCQAエグゼクティブサマリー | Situation-Complication-Question-Answer | `as_is` / `challenges` / 採択案 |
| 2 | As-Is vs To-Be 対比 | 現状と理想の対比、KPIの現状値→目標値。外部から見える姿と現場実態を並べる(**下記のリフレーミング規約に従う**) | `as_is`(public/internal) / `to_be` / `kpis` |
| 3 | GAPと真因 | 状態の乖離と、その裏にある真因。**なぜ今まで解決に至っていないか**(既往の取り組みと頓挫理由) | `gaps` / `bottlenecks` / `attempts` |
| 4 | 打ち手比較と選定理由 | Impact × Feasibility マトリクス + **なぜ他案を落としたか** | `mini-prfaq` / `rejected_options` |
| 5 | 推奨ソリューション詳細 | 選定案の具体像(How・Workflow Before/After)。**複数枚に展開してよい** | `prfaq` の技術的背景・workflow改善見込み |
| 6 | ロードマップ | 段階と、各段階がどの仮説の検証に依存するか | `hypotheses` / `decision-roadmap` |
| 7 | ネクストアクション(Ask) | **本日合意いただきたい事項**(PoC実施・体制・スコープ・次工程) | `open_questions` / `hypotheses(unvalidated)` |

複雑な図解はMermaidまたは対比テーブルに割り切る(Marpの表現力の範囲内に収める)。

### 認識GAPのリフレーミング規約(章2)

**相互レビュー(agy)の指摘により追加。提案関係の破綻を防ぐための必須規約。**

認識GAP(公開情報から見える姿 と 現場実態 の乖離)をそのまま「言動不一致の暴露」として提示すると、顧客の防衛反応(恥・脅威・責任追及への恐れ)を招き、対話が閉じる。標榜していることと現場実態の乖離を不用意に突くと、組織は自己防衛のために隠蔽・反発に走る(Argyrisの組織防衛論)。

`make-slides` は認識GAPを出力する際、**非難を伴わない表現へ変換する**:

| 変換前(そのまま出すと防衛を招く) | 変換後 |
|---|---|
| 「対外的には〇〇と説明しているが、実態は△△」 | 「外部環境の変化スピードに対し、現場の仕組みの追随には□□のタイムラグがある」 |
| 「公約と実態が乖離している」 | 「目指す姿と、現在の運用上の摩擦点」 |

**責任の所在ではなく、環境変化と適応のタイムラグとして描く**。これは事実を歪める操作ではなく、同じ事実を協調的探索の枠組みで提示する編集判断である(引用する `as_is` ノードと出典は変えない)。

#### 誠実さを損なわないための線引き(agy指摘により追加)

リフレーミングは容易に「不誠実な美化」に堕ちる。実態を吐露した現場担当者から見て「経営陣に忖度して痛みを薄められた」と映れば、共感の獲得どころか信頼を失う。**次の峻別基準を守る**:

| 外すもの | 保つもの |
|---|---|
| **誰が悪いか**(責任の所在・individual/部門の名指し) | **何が起きているか**(構造的弊害の深刻度・頻度・影響範囲) |
| 非難・断罪のトーン | 数値・事実・当事者の痛みの生々しさ |

**「タイムラグ・摩擦」への画一的な言い換えは禁止する**。実態が `blocker_category: politics_incentive`(部門間の利害対立)や意図的なサボタージュである場合、環境変化の物語に押し込めると問題の矮小化(コーポレート・スピーク化)になり、真因が議題から消える。この場合は**利害構造そのものを非人格的に描く**(「〇〇部が抵抗している」ではなく「現行の評価指標が部門間で相反しており、片方の改善が他方の不利益になる構造」)。

適用範囲は `slides` に限らず、**顧客提出物である `prfaq` の文章生成にも同じ規約を適用する**。

---

## 8. 優先度・効果比較

単一の数値スコアはLLMの恣意的な採点になりやすく、過剰な数式化は軽さを失う(Codex/agy が独立に指摘)。

- **impact**: フェルミ推定の結果を参照(`fermi` artifact ID)。LLMが数値を作らない。`kpis` の目標値と結びつける
- **feasibility**: 技術ナレッジの確度 + `constraints` との突合
- **保存形式**: 「基準・根拠・確度」を持つ比較表として保存し、数値効果はフェルミ生成物への参照に留める

**感度分析**: `Hypothesis.fermi_ref`(3.6)により、「どの仮定がブレると効果の桁が変わるか」を決定論的に算出できる。これが `decision-roadmap` の検証優先度になる。

---

## 9. フェーズ2の優先順位

| 優先度 | 項目 | 備考 |
|---|---|---|
| **1** | 論理構造スキーマ + ID規約 + 移行 + 充足状況の可視化 + **`medo-hearing` の改訂** | ID採番シーケンス(3.1)・型付きリンク・`covered_challenge_ids` を含める。これが無いと2を開始できない。**Skillが `process_checks` を読んで未確認項目をどう扱うかの契約(質問する/明示的に保留する/例外として記録する)を受入条件に含める**(Codex指摘。スキーマだけ作ってもSkillが使わなければ確認プロセスは実行されない) |
| **2** | 陳腐化のセクション単位化 + カバレッジ判定 + 2段階重大度 | 1と密結合。飛ばすと全生成物が常時stale化して破綻 |
| **3** | 出典検証の強化(URLフェッチ + 数値突合) | **他と技術的に独立しており並行可能**。Task10で穴を実証済み |
| **4** | 生成物の依存グラフ + stale伝播 | `make-slides` の前提 |
| **5** | `make-slides`(7章構成の構造化テンプレート) | 利用者の主要求 |
| **6a** | ナレッジ来歴スキーマ | **6bの前提**(下記) |
| **6b** | `knowledge-digest`(LLMによる統合提案) | 統合後も旧entryを残し、過去Artifactの引用が検証可能であること |
| **7** | `decision-roadmap`(再定義) | 3.6の `fermi_ref` が前提。感度分析と連動 |
| 後続 | `build-mock` / `propose-architecture` / pricing(再定義) / 簡易Webアプリ | フェーズ2完了定義の改訂が必要(後述) |

### 優先度6a: ナレッジ来歴スキーマの仕様

現行 `KnowledgeStore.save` は同一 `entry_id` でファイルを**上書きする**ため、統合すると原本が消え、過去のPRFAQ・スライドの引用(`cited_knowledge`)が解決不能になる。

```python
class KnowledgeEntry(BaseModel):
    # --- 追加 ---
    supersedes: list[str] = []      # このエントリが統合・置換した旧エントリID
    superseded_by: str = ""         # 後継エントリID(旧エントリ側に記録)
```

- **旧エントリは削除せず不変で残す**。`superseded_by` を追記するのみ
- `medo knowledge search` は既定で `superseded_by` が設定されたエントリを除外する(`--include-superseded` で含める)
- **過去Artifactの引用IDは常に解決可能**であることを不変条件とする。`status` は旧エントリを引用する生成物を「後継あり」として `outdated` で報告する(欠落ではないため `stale` にしない)
- 案件固有ナレッジ(markdown / sqlite の2バックエンド)にも同じ規約を適用する

### 相互レビューで訂正された当初案の誤り

- **pricing計算機の削除は誤り**: 「クラウド非依存」は「料金を扱わない」ことを意味しない。不正だったのはテスト方針(単一の公式Calculatorを正解に置けない)であり機能の要否ではない。**再定義して後送り**
- **簡易Webアプリの除外根拠が誤り**: 正本 `medo-design.md` はフェーズ2に明記しており、差別化軸の「単一のWebアプリに閉じる」は「Webアプリを作らない」という意味ではない。**優先度を下げるが除外しない**

### フェーズ2完了定義の改訂(要承認)

現行は「課題→What/Why合意→スライド+モックまで半日」だが、`build-mock` を後続に送るため改訂が必要:

> **改訂案**: 課題→What/Why合意(MECEな構造の充足を確認)→共感できるドキュメント+提案スライド(7章構成)まで半日。knowledgeが案件を跨いで洗練される。

---

## 10. 未決事項

1. 重複検知(MECEのE)を `knowledge-digest` と実装共有するか、別機能にするか
2. 差別化の訴求(証跡追跡可能性をMoatとして押し出す)を正本のどこに書くか。**競合ツールの具体的な弱点は未検証のため、出典なしにドキュメントへ書かない**
3. `decision-roadmap` の出力形式(生成物typeを新設するか、既存の `comparison` を使うか)
4. **Strawman提示のバイアス誘導リスクへの対処**(agy指摘・未解決)。Skillが公開情報から作る仮説の精度が低いと初期信用を失い、逆に顧客が迎合的だと誤った仮説が実態として固定化される。`confidence: assumed` での提示と明示的な確認は前提だが、精度が低い場合の撤退基準は未定
5. **`ProcessChecks` の状態をSkillが会話ログから正確に判定・更新できるか**(agy指摘・未検証)。`unverified` と `confirmed_none` の区別は判定難易度が高く、手動介入のオーバーヘッドが生じうる。実案件で検証する
