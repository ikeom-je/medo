# フェーズ2 ワークフローモデル

標準周回の**進行記録**と**収束規則**。索引: [medo-phase2-design.md](medo-phase2-design.md)

**この層は案件の内容を持たない**。内容の正本は[ドメインモデル](phase2-domain-model.md)にある。

---

## 1. なぜ要件と分けるのか

進行記録(レビュー・顧客の反応・チェックポイント)を `RequirementsDoc` の中に置くと**論理的に破綻する**。

要件は保存のたびに版が進む。v3への反応を記録するとその保存自体がv4を作り、**記録した瞬間に「旧版宛て」になる**。「現行版への合意」を収束条件にできない。

したがって進行記録は**要件の版とは独立した追記型イベント**として持つ。

```
projects/{id}/requirements/v{n}   ← 内容の正本(版が進む)
projects/{id}/events/{ev_id}      ← 進行記録(追記のみ)
projects/{id}/artifacts/{type}-v{n}
```

---

## 2. イベントモデル

進行記録は4種類あり、**共通のenvelope + 型別payload**で表す。4つを1つの曖昧な汎用イベントに潰さず、共通部分だけを共有する。

```python
class ArtifactTarget(BaseModel):
    kind: Literal["artifact"] = "artifact"
    artifact_id: str            # 例: "as-is-report-v2"

class RequirementsTarget(BaseModel):
    kind: Literal["requirements"] = "requirements"
    version: int

TargetRef = Annotated[ArtifactTarget | RequirementsTarget, Field(discriminator="kind")]


class WorkflowEventBase(BaseModel):
    id: str = ""                 # ev-N(プロジェクト内で単調増加)
    target: TargetRef
    occurred_on: str             # ISO日付
    requirements_version: int    # 記録時点の最新要件版
```

`TargetRef` を判別共用体にすることで、`target_kind` と `target_id` / `target_version` の排他制約がスキーマで保証される。

### 4つのイベント型

```python
class DiscoveryCheckRecorded(WorkflowEventBase):
    kind: Literal["discovery_check"] = "discovery_check"
    check: Literal["reality_gap", "past_attempts", "hidden_stakeholders", "decision_maker"]
    result: Literal["confirmed_none", "identified"]

class AsIsReportReviewed(WorkflowEventBase):
    kind: Literal["asis_review"] = "asis_review"
    outcome: Literal["approved", "changes_requested"]
    finding_refs: list[str] = []   # gap / challenge / open_question のID

class StakeholderResponded(WorkflowEventBase):
    kind: Literal["response"] = "response"
    stakeholder_id: str
    purpose: Literal["as_is_alignment", "to_be_go_ahead", "phase_signoff"]
    reaction: Literal["empathized", "acknowledged", "agreed", "objected", "unclear"]
    note: str = ""

class ToBeCheckpointRecorded(WorkflowEventBase):
    kind: Literal["tobe_checkpoint"] = "tobe_checkpoint"
    answer: Literal["generate", "defer"]
```

**共通envelopeにしたことで、すべての進行記録に対象・日付・周回が付く**。当初案は `ProcessChecks` と `ToBeDecision` を要件内のスナップショットに、`AsIsReview` と `Confirmation` を外部イベントに、と偶然分裂させていた。意味の似た4概念が保存場所で分かれており、イベント追加時に要件内のチェックポイントをどう更新するかが定義できなかった。

### 反応の目的(purpose)

**「何に対する合意か」を記録する**。同じ `agreed` でも「現状認識に納得した」と「次工程へ進むことを承認した」は別物である。

| purpose | 意味 | 必要な場面 |
|---|---|---|
| `as_is_alignment` | 現状認識のすり合わせ | ステージ3の通常の反応 |
| `to_be_go_ahead` | この理想像で検討を進めてよい | ToBe確定時 |
| `phase_signoff` | フェーズを完了して次へ進む承認 | 収束判定 |

**共感(Buy-in)と合意(Sign-off)は別物である**。「共感はしたが進めることに合意した覚えはない」という梯子外しを防ぐため、`reaction` でも `empathized` と `agreed` を分ける。要求の確認と承認を別タスクとして扱うのは上流工程の標準的な整理である([BABOK Guide](https://www.iiba.org/standards-and-resources/babok-guide/))。

### 認証は導入しない

`StakeholderResponded` は**利用者本人が、対話の結果として得た他者の反応を記録する**ものであり、他者がシステムにログインして入力するものではない。したがって記録は「**本人が報告した反応**」であって、本人性を検証した事実ではない。`stakeholder_id` は既存の `stakeholders` を指し、新たな利用者概念を作らない。

**保存時の検証**: `stakeholder_id` と `target` が同一プロジェクトに実在すること。

---

## 3. 現在の収束対象

**収束判定は「現在の対象」に対してのみ行う**。これが無いと、旧版への異議で永久に止まり、逆に古い版への合意で誤って通る。

```python
class ConvergenceTarget(BaseModel):
    requirements_version: int       # 最新の要件版
    as_is_report_id: str            # 最新の as-is-report
```

`medo status` が最新状態から**決定論的に導出する**(保存しない)。

### 版をまたぐ反応の畳み込み

同一ステークホルダーの反応は、**対象の系列ごとに最新のものを有効値とする**。

> **有効な反応の決定**: 同一 `stakeholder_id` × 同一 `purpose` について、**現在の収束対象またはその祖先**を対象とする `StakeholderResponded` のうち、`id` の採番順で最後のものを有効値とする。

**祖先を含めるのが要点である**。`as-is-report-v1` への異議は、同じ相手が `as-is-report-v2`(v1の後継)に反応を記録した時点で**superseded** となり、有効値から外れる。当初案は「同一target」に限定していたため、v1で異議が出た後にv2で修正して合意を得ても**v1の異議が永久に残り、収束条件を一生満たせなかった**。

後継関係は生成物の版(`as-is-report-v1` → `v2`)と要件の版で判定する。祖先への反応しか無い場合はそれを有効値とし、現在対象への反応が記録されたら置き換わる。

**旧版への異議は履歴として残る**。有効値から外れるだけで、削除も改変もしない。

---

## 4. ToBeチェックポイント

往復の周回をSkillが勝手に決めない。**現実が仮説を押し返した節目で、ユーザーに「ToBeを出す/更新するか」の判断を求める**。

### 記録は毎回、問いかけは節目で

保存のたびにSkillが会話を止めて問うと、対話が寸断され確認疲れを招く。そこで**記録の層と問いかけの層を分ける**。

| 層 | 発火 | 振る舞い |
|---|---|---|
| **記録(データ)** | 下記の節目条件が成立した操作 | `ToBeCheckpointRecorded` の未回答状態(`pending`)が立つ |
| **問いかけ(会話)** | 同じ節目条件 | Skillが `workflow.loop` を提示して問う。節目でない操作ではCLI出力に現在地を1行添えるに留める |

**`pending` は単一の発火規則で決まる**。当初案は「as_isが変更された保存」「節目条件のいずれか」「節目でなくても蓄積」の3つの異なる記述を持ち、実装者が判定できなかった。**節目条件の成立が唯一の発火条件**である。

`pending` は次の `ToBeCheckpointRecorded`(回答)まで解消しない。節目でない操作が続いても既存の `pending` は残るため、**問わずに先へ進んだ履歴は失われない**。

### 節目の条件(決定論)

節目とは**現実が仮説を押し返した瞬間**である。直前の状態との差分で次のいずれかが新たに発生したとき、`pending` を立てる。

| # | 条件 | 発生源 |
|---|---|---|
| 1 | `internal` の AsIs が初めて追加された(0件 → 1件以上) | 要件保存 |
| 2 | `Gap(kind="perception")` が新規に追加された | 要件保存 |
| 3 | `Gap(kind="internal_conflict")` が新規に追加された | 要件保存 |
| 4 | `constraints` が新規に追加された | 要件保存 |
| 5 | `outcome` が `stalled` / `failed` の `Attempt` が新規に追加された | 要件保存 |
| 6 | `stance="resistant"` または `is_decision_maker=True` の `Stakeholder` が新規に追加された | 要件保存 |
| 7 | `AsIsReportReviewed(outcome="changes_requested")` が記録された | **イベント記録** |
| 8 | `StakeholderResponded(reaction="objected")` が記録された | **イベント記録** |

**条件7・8は要件保存を伴わずに発生する**。イベントは要件とは独立した追記型ストアに記録されるため、**イベントの記録操作自体が `pending` を立てる**。イベントストアが独立していることで、要件の版を進めずにチェックポイントを更新できる(当初案は要件内のスナップショットを更新しようとして、更新先が定義できなかった)。

いずれも「そのToBeは無理だ」という現実の反応、または**AsIs自体の不整合が露見した地点**であり、仮説を見直す意味を持つ。単なる本文の微修正や既存項目の言い換えは節目にしない。

**条件2〜8が示すとおり、節目はAsIsの変化だけでは決まらない**。プローブとしてのToBeをぶつけて噴出する暗黙知の大半は、現状そのものではなく**制約と組織力学**である。「そのToBeは無理」の主因は業務フローよりも、法務・親会社の内規や特定部門長の反対であることが実務上多い。

---

## 5. AsIsレビュー

**毎周のレビュー記録を必須にしない**。少人数の案件で毎回手動記録を義務づけると、中身のない定型入力を量産して形骸化する。

- **記録するのは `changes_requested` のとき**(所見がある場合)。`finding_refs` を必須とする
- `approved`(問題なし)の記録は任意。記録しない場合、構造診断([status契約](phase2-status-contract.md)の `model.links`)が代替の検出手段になる
- 収束条件は「レビューが存在すること」ではなく「**未解決の `changes_requested` が無いこと**」とする

**`changes_requested` の解消**: 同じ `as-is-report` 系列の後継に対して `approved` が記録されるか、`finding_refs` が指すノードがすべて解消(削除または `confidence: confirmed` へ)されたとき。当初案は「レビューが存在する」だけで収束条件を満たしたため、所見が未解決でも通ってしまった。

---

## 6. 発見プロセスの確認

AsIsに暗黙知が入らないままToBeを確定させると理想の正論に終わる。これを防ぐ3つの確認プロセスをSkillの契約とする。実施結果は `DiscoveryCheckRecorded` イベントに記録する。

| check | 問うこと | 組織防衛を招かない問い方 |
|---|---|---|
| `reality_gap` | 公開情報から見える姿を現場実態と突き合わせたか | 「対外的にはこう見えていますが実態は」ではなく「**目標達成に向けて、現場で直面している想定外の制約は何でしょうか**」 |
| `past_attempts` | その課題にこれまで取り組んだか、なぜ進まなかったか | — |
| `hidden_stakeholders` | 影響を受ける人・承認が必要な人が他にいないか | — |
| `decision_maker` | 決裁権限を持つのは誰か | — |

**`reality_gap` の問い方には注意が要る**。標榜していることと現場の実態の乖離を不用意に突くと、組織は自己防衛のために隠蔽・反発に走り対話が閉じる(Argyrisの組織防衛論)。告発・尋問と受け取られない**協調的探索の問い**に変換する。

**「未確認」と「確認したが該当なし」を区別する**。データの形から確認プロセスの実施を推測すると誤判定になる — 推定した関係者を1件置くだけで警告が消え、逆に質問して「他にいない」と確認した正常なケースでは永続的に警告され続ける。したがって `result: confirmed_none | identified` を明示的に記録する。

**`identified` に対応するレコード**(整合検証に使う):

| check | `identified` が意味するもの |
|---|---|
| `reality_gap` | `Gap(kind="perception")` が1件以上 |
| `past_attempts` | `Attempt` が1件以上(`outcome` は問わない) |
| `hidden_stakeholders` | `Stakeholder(surfaced_by="inferred")` が1件以上 |
| `decision_maker` | `Stakeholder(is_decision_maker=True)` が1件以上 |

`identified` なのに対応レコードが0件、または `confirmed_none` なのに対応レコードが存在する場合は**不整合**として報告する。

---

## 7. 収束の判定

**収束を決めるKPI/KGIは暗黙知に依存し、人間自身も認知していない場合がある**。したがって構造的条件だけでは「一定の精度に達した」と判断できず、**人間が確認し合意した事実**が最終的な根拠になる。

判定は[status契約](phase2-status-contract.md)の `readiness` が返す。**現在の収束対象**(§3)に対してのみ計算する。

### 肯定条件(すべて満たすこと)

違反が無いことは準備が整っている証明にならない。**肯定条件を明示的に合成する**。

| # | 条件 | 失敗時の理由コード |
|---|---|---|
| 1 | `scope: core` の `internal` AsIs が1件以上 | `internal_as_is_missing` |
| 2 | `scope: core` の `to_be` に `confirmed` が1件以上あり、そのすべてが裏づけ済み | `unsupported_confirmed_to_be` |
| 3 | `DiscoveryCheckRecorded` が4つの check すべてについて存在する | `discovery_check_missing` |
| 4 | 未解決の `changes_requested` が無い | `review_findings_open` |
| 5 | 決裁者(`is_decision_maker=True`)から `purpose="phase_signoff"` の `agreed` が得られている | `decision_maker_signoff_missing` |
| 6 | `influence="high"` のステークホルダーに、有効値としての `objected` が残っていない | `high_influence_objection_open` |

**条件2の「裏づけ済み」の判定式**: ToBeと内部実態を結ぶ経路を既存の `Gap(kind="goal")` で定義する。

> **ToBe `tb-N` が裏づけを持つ** ⟺ `from_to_be` に `tb-N` を含む `Gap(kind="goal")` が存在し、その `from_as_is` に `visibility="internal"` かつ `confidence != "open"` の AsIs が1件以上含まれる

**条件5・6が収束判断の中核である**。単なる頭数では判定しない — 現場担当者2名の共感で通る一方、決裁者が未確認でも通り、影響力の無い1名の異議で全体が止まる、という誤判定を防ぐ。

**これは保存ゲートではなく診断である**。条件を満たさなくてもPRFAQやスライドの生成は妨げない。

### 往復の発散

`round_count` が3を超えても `to_be` の `confirmed` が増えない状態を **発散の疑い**として報告する。論点の発散、ステークホルダー間の対立、スコープ肥大化の兆候になる。実務上の有効な往復は2〜3周が目安である。

**収束の目安**: 新規に得られた実態によってToBeの修正差分が出なくなった状態(飽和)。

`round_count` は `as_is` の変更と `to_be` の変更が交互に起きた回数として、要件バージョンの履歴から決定論的に導く。発散の報告は**停止条件ではない**。
