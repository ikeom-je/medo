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

進行記録は5種類あり、**共通のenvelope + 型別payload**で表す。1つの曖昧な汎用イベントに潰さず、共通部分だけを共有する。

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
    round_id: int                # 記録時点の周回(§7のアルゴリズムで導出)
```

**`round_id` を全イベントが持つ**。当初案は `MilestoneDetected` だけが持っていたため、反応やチェックがどの周回に属するかを一意に決められず、`round_delta`(§7)を決定論的に算出できなかった。要件版とイベントIDは別系列であり、両者から周回を推定することはできない。

`TargetRef` を判別共用体にすることで、`target_kind` と `target_id` / `target_version` の排他制約がスキーマで保証される。

### 5つのイベント型

```python
class CheckRecorded(WorkflowEventBase):
    kind: Literal["check"] = "check"
    check: CheckItem                    # §6のチェック項目
    result: Literal["completed", "finding", "undeterminable"]
    note: str = ""                      # finding / undeterminable のとき必須
    finding_refs: list[str] = []        # finding のとき、該当するノードID
    disposition: Literal["open", "deferred", "promoted"] = "open"   # undeterminable の扱い(§6)

class AsIsReportReviewed(WorkflowEventBase):
    kind: Literal["asis_review"] = "asis_review"
    outcome: Literal["approved", "changes_requested"]
    finding_refs: list[str] = []   # gap / challenge / open_question のID(要件側の所見)
    slide_findings: list[str] = [] # スライド固有の所見(表現・構成。自由文)
    reviewed_slides_id: str        # 同時にレビューした討議用スライドのID(必須)
    reviewed_by: Literal["claude", "codex", "gemini", "human"] = "human"

class StakeholderResponded(WorkflowEventBase):
    kind: Literal["response"] = "response"
    stakeholder_id: str
    purpose: Literal["as_is_alignment", "to_be_go_ahead", "phase_signoff"]
    reaction: Literal["empathized", "acknowledged", "agreed", "objected", "unclear"]
    note: str = ""

class MilestoneDetected(WorkflowEventBase):
    kind: Literal["milestone"] = "milestone"
    condition: MilestoneCondition          # §4の10条件のいずれか
    focus_hypothesis_id: str = ""          # この周回で検証する論点(任意)

class ToBeCheckpointRecorded(WorkflowEventBase):
    kind: Literal["tobe_checkpoint"] = "tobe_checkpoint"
    answer: Literal["generate", "defer"]
    responds_to: str                       # 回答対象の MilestoneDetected のイベントID
```

**節目の検出自体をイベントにする**。当初案は `ToBeCheckpointRecorded` が回答しか持たないのに「同イベントの未回答状態が立つ」と説明しており、**未回答状態がどのデータから導かれるのかが定義できていなかった**。節目を `MilestoneDetected` として記録し、回答を `responds_to` で紐づけることで、未回答は「対応する `ToBeCheckpointRecorded` を持たない `MilestoneDetected`」として一意に導ける。

`focus_hypothesis_id` は `MilestoneDetected` が持つ(周回ごとの検証論点)。`round_id` は envelope が持つ(上記)。

**`round_id` の採番**: イベントを記録する時点で、§7 の `round_count` アルゴリズムを最新の要件履歴に適用して得た値を入れる。これにより `round_count` と `max(round_id)` が一致する。

**`focus_hypothesis_id` の設定**: `medo checkpoint answer --focus <hyp-id>` で指定する。指定が無ければ直前の `MilestoneDetected` の値を引き継ぐ(周回をまたぐまで同じ論点を追う)。参照先が実在する仮説であることを保存時に検証する。

**保存時の検証**: `ToBeCheckpointRecorded.responds_to` が実在する `MilestoneDetected` のIDであり、まだ回答されていないこと(二重回答を防ぐ)。

**記録の冪等性**: 要件保存とイベント記録は別ストアであるため、要件保存後に `MilestoneDetected` の記録が失敗する可能性がある。**`(requirements_version, condition)` の組で重複を排除する** — 同じ版の同じ条件に対する `MilestoneDetected` は1件しか作らない。再試行しても重複しない。

### イベント型ごとの許容target

判別共用体だけでは、すべてのイベントが両方のtargetを取れてしまう。**型ごとに固定する**。

| イベント型 | 許容する target |
|---|---|
| `CheckRecorded` | `requirements`(スライド表現のチェックのみ `artifact`) |
| `AsIsReportReviewed` | `artifact`(`as-is-report` のみ) |
| `StakeholderResponded` | `purpose` により決まる(§3) |
| `MilestoneDetected` | `requirements` |
| `ToBeCheckpointRecorded` | `requirements` |

`StakeholderResponded` の許容targetは purpose で決まる(§3)。`phase_signoff` のみ `artifact` を取る。

**保存時の検証**:

- 上表の target 組み合わせ
- `AsIsReportReviewed(outcome="changes_requested")` は `finding_refs` と `slide_findings` の**いずれかが非空**であること。`finding_refs` を使う場合は記録時点の要件版に実在すること
  - **スライド固有の差し戻しを要件ノードで表せないため**(agy指摘)。「見出しの表現がリフレーミング規約に反する」といった所見は要件の欠陥ではなく、要件側にダミーの `open_question` を捏造しないと保存できない状態だった
- `AsIsReportReviewed.reviewed_slides_id` は**必須**とし、`slide_kind="discussion"` の `slides` で、かつ `derived_from` に当該 `as-is-report` を含むこと(レポートとスライドを必ず一緒にレビューする契約と整合させる)

**共通envelopeにしたことで、すべての進行記録に対象・日付が付く**。当初案は `ProcessChecks` と `ToBeDecision` を要件内のスナップショットに、`AsIsReview` と `Confirmation` を外部イベントに、と偶然分裂させていた。意味の似た概念が保存場所で分かれており、イベント追加時に要件内のチェックポイントをどう更新するかが定義できなかった。

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
    as_is_report_id: str | None     # 最新要件版から生成された as-is-report(無ければ None)
```

`medo status` が最新状態から**決定論的に導出する**(保存しない)。

**`as_is_report_id` は「最新要件版から生成された最新の `as-is-report`」に限定する**。要件版とレポートを独立に選ぶと、古い要件から作られたレポートが現在対象になり、両者が食い違う。該当するレポートが存在しない場合は `None` とし、`readiness` は `as_is_report_missing` を返す。

### purpose ごとに対象の種別を固定する

反応がどちらの種別を対象にするかを固定しないと、要件宛てと生成物宛ての反応が混在して畳み込みが壊れる。

| purpose | 許容する target | 意味 |
|---|---|---|
| `as_is_alignment` | `artifact`(`as-is-report` のみ) | 共有した現状認識への反応 |
| `to_be_go_ahead` | `requirements` | この理想像で検討を進めてよい |
| `phase_signoff` | `artifact`(`slides` の `slide_kind="final"` のみ) | フェーズを完了して次へ進む承認(§7 phase_readiness) |

保存時にこの組み合わせを検証する。

### 版をまたぐ反応の畳み込み

同一ステークホルダーの反応は、**対象の系列ごとに最新のものを有効値とする**。

> **有効な反応の決定**: 同一 `stakeholder_id` × 同一 `purpose` について、**現在の収束対象またはその祖先**を対象とする `StakeholderResponded` から、次の順で1件を選ぶ。
>
> 1. **現在の収束対象を対象とするもの**があれば、そのうち `id` の採番順で最後のもの
> 2. 無ければ、祖先を対象とするもののうち **`target` の `requirements_version` が最大**のもの。同値なら `id` の採番順で最後のもの

**現行版への反応を祖先への反応より常に優先する**(Codex指摘による訂正)。祖先全体から単純に `id` 順で選ぶと、**現行版に反応を得た後で旧版の反応を追記した場合に、古い内容への反応が現行版の反応を上書きしてしまう**。記録の順序ではなく対象の新しさで優先する。

**祖先を含めるのが要点である**。`as-is-report-v1` への異議は、同じ相手が `as-is-report-v2`(v1の後継)に反応を記録した時点で**superseded** となり、有効値から外れる。当初案は「同一target」に限定していたため、v1で異議が出た後にv2で修正して合意を得ても**v1の異議が永久に残り、収束条件を一生満たせなかった**。

**祖先の判定は `requirements_version` の単調性で行う**(生成物の版番号だけでは判定できない — 生成物の版は type別の採番にすぎず、古い要件版から新しい版番号のレポートを作ることを禁止していないため)。

- `artifact` 対象: 同じ `type` の生成物のうち、`requirements_version` が現在対象**以下**のものを祖先とする
- `requirements` 対象: `version` が現在対象**以下**のものを祖先とする

**畳み込みキーは `(stakeholder_id, purpose)` である**。target種別は purpose で固定されているため、キーに含める必要がない。

**旧版への異議は履歴として残る**。有効値から外れるだけで、削除も改変もしない。

### 祖先への合意は内容が変わったら失効する

祖先への反応を無条件に有効とすると、**v1で得た合意が、v2で内容が大きく変わっても有効なまま残る**(agy指摘)。「古い合意で誤って通る」を防ぐという目的と矛盾する。

> **祖先への `agreed` / `empathized` は、その合意が依存するセクションに `substantive` な変更が無い場合にのみ継承する**。該当セクションに実質変更([ドメインモデル](phase2-domain-model.md) §7 の変更manifest)があれば、その合意は失効し `re_confirmation_required` として報告する。

**失効の判定はセクション単位で行う**(agy指摘による訂正)。「途中に `substantive` な変更が1つでもあれば失効」とすると、**`to_be_go_ahead` を得た後に無関係な `constraints` や `stakeholders` へ実態を追記しただけで合意が巻き添え失効し**、再び収束不能ループに陥る。陳腐化判定がセクション単位であるのと同じ粒度にする。

| purpose | 失効を引き起こすセクション |
|---|---|
| `as_is_alignment` | 対象 `as-is-report` の依存セクション(`as_is` / `gaps` / `constraints` / `stakeholders` / `attempts`) |
| `to_be_go_ahead` | `to_be` / `kpis` / `goal` |
| `phase_signoff` | 対象の最終提案スライドとその親 `prfaq` の依存セクション |

**`objected` は逆で、内容が変わっても継承する**(解消されたことが確認できるまで残す)。安全側に倒す。

### 上位のpurposeでの合意は下位の異議を包括解消する

`as_is_alignment` に異議を述べた相手が、改訂版を見て `to_be_go_ahead` に合意した場合、**先行の懸念は包括的に解消されたとみなすのが実務の自然な流れ**である。`(stakeholder_id, purpose)` の完全一致だけで畳み込むと、過去の異議が解消されないまま残り続ける。

> **purposeには順序がある**: `as_is_alignment` < `to_be_go_ahead` < `phase_signoff`
>
> 同一 `stakeholder_id` について、**より上位の purpose で `agreed` が有効値になっている場合、それより下位の purpose の未解決 `objected` は subsumed(包括解消)として有効値から外す**。

包括解消も履歴には残り、`workflow.responses` で `subsumed_by` として参照できる。

**生成物の保存時に `requirements_version` の単調性を検証する**: 同じ type の既存最新版より古い `requirements_version` での保存を拒否する(祖先判定が壊れるため)。

---

## 4. ToBeチェックポイント

往復の周回をSkillが勝手に決めない。**現実が仮説を押し返した節目で、ユーザーに「ToBeを出す/更新するか」の判断を求める**。

### 記録は毎回、問いかけは節目で

保存のたびにSkillが会話を止めて問うと、対話が寸断され確認疲れを招く。そこで**記録の層と問いかけの層を分ける**。

| 層 | 発火 | 振る舞い |
|---|---|---|
| **記録(データ)** | 下記の節目条件が成立した操作 | core が `MilestoneDetected` を記録する |
| **問いかけ(会話)** | 同じ節目条件 | Skillが `workflow.loop` を提示して問う。節目でない操作ではCLI出力に現在地を1行添えるに留める |

**`pending` は単一の規則で導出される**。当初案は「as_isが変更された保存」「節目条件のいずれか」「節目でなくても蓄積」の3つの異なる記述を持ち、実装者が判定できなかった。

> **`pending` の導出**: `MilestoneDetected` のうち、その `id` を `responds_to` に持つ `ToBeCheckpointRecorded` が存在しないものの集合。空でなければ `checkpoint.state = "pending"`。

`pending` は回答が記録されるまで解消しない。節目でない操作が続いても既存の `pending` は残るため、**問わずに先へ進んだ履歴は失われない**。

**発火の判定順序**: 要件保存とイベント記録の2つのストアにまたがるため、共通のカーソルを定める。

- 要件保存による節目(条件1〜6・9・10)は、`RequirementsStore.save` の完了後に core が差分から判定して `MilestoneDetected` を記録する(`requirements_version` は保存後の版)
- イベント記録による節目(条件7〜8)は、そのイベントの記録直後に core が `MilestoneDetected` を記録する(`requirements_version` は記録時点の最新版)
- 同一の要件保存で複数条件が成立した場合は、**`MilestoneDetected` を1件だけ記録し `condition` に最初に成立した条件を入れる**(1回の保存に対して問いかけは1回でよい)

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
| 9 | `Hypothesis.status` が `validated` へ変わった | 要件保存 |
| 10 | `ToBe.confidence` が `confirmed` へ昇格した | 要件保存 |

**条件7・8は要件保存を伴わずに発生する**。イベントは要件とは独立した追記型ストアに記録されるため、**イベントの記録操作自体が `MilestoneDetected` を記録する**。イベントストアが独立していることで、要件の版を進めずにチェックポイントを更新できる(当初案は要件内のスナップショットを更新しようとして、更新先が定義できなかった)。

条件1〜8は「そのToBeは無理だ」という現実の反応、または**AsIs自体の不整合が露見した地点**である。

**条件9・10は前向きな前進を捉える**(agy指摘により追加)。当初案は節目を「現実が押し返した瞬間」に限定していたため、**対話が順調に進んで仮説が支持され、ToBeが確定に向かう場合にチェックポイントが発火せず、次のステージへ進むトリガーが作られなかった**。実務上の節目は押し返されたときだけでなく、**仮説が検証されて案が固まったとき**も等しく重大な分岐点である。

単なる本文の微修正や既存項目の言い換えは節目にしない。

**条件2〜8が示すとおり、節目はAsIsの変化だけでは決まらない**。プローブとしてのToBeをぶつけて噴出する暗黙知の大半は、現状そのものではなく**制約と組織力学**である。「そのToBeは無理」の主因は業務フローよりも、法務・親会社の内規や特定部門長の反対であることが実務上多い。

---

## 5. AsIsレビュー

**レビュー対象は `as-is-report` と討議用スライドの両方である**(agy指摘)。当初案は対象をレポートのみとし、スライドはステージ3で生成・提示する設計だったが、**顧客との関係破綻リスクが最も高くリフレーミング規約が課されているのはスライドの方**である。レポート本文が安全でも、Marpスライドへ要約する過程で攻撃的な見出しが生成されうる。顧客に投影する資料を事前チェックせずに会議へ持ち込む運用は実務では成立しない。

したがって**討議用スライドの生成はステージ1の終盤で行い、ステージ2でレポートと共にレビューする**。`reviewed_slides_id` にレビューしたスライドのIDを記録する。

**毎周のレビュー記録を必須にしない**。少人数の案件で毎回手動記録を義務づけると、中身のない定型入力を量産して形骸化する。

- **記録するのは `changes_requested` のとき**(所見がある場合)。`finding_refs` を必須とする
- `approved`(問題なし)の記録は任意。記録しない場合、構造診断([status契約](phase2-status-contract.md)の `model.links`)が代替の検出手段になる
- 収束条件は「レビューが存在すること」ではなく「**未解決の `changes_requested` が無いこと**」とする

**`changes_requested` の解消**: 同じ `as-is-report` 系列の後継に対して `approved` が記録されたとき。`finding_refs` が指すノードがすべて解消(削除または `confidence: confirmed` へ)された場合も解消とする。`slide_findings`(自由文)は機械判定できないため、**後継への `approved` でのみ解消する**。当初案は「レビューが存在する」だけで収束条件を満たしたため、所見が未解決でも通ってしまった。

---

## 6. チェックリスト

AsIsに暗黙知が入らないままToBeを確定させると理想の正論に終わる。これを防ぐ確認項目をSkillの契約とし、実施結果を `CheckRecorded` イベントに記録する。

### チェックリストの正本はCLI側に置く

**項目の定義と結果の記録はCLIが持ち、各ドキュメントにはその時点で関連する項目を投影する**。ドキュメント本文にチェックリストを埋め込むと、更新が4種類の文書に分散し、記録が本文に埋まってCLIが未確認を検出できなくなる。これは移植性の条件1・4([Skill構成と移植性](phase2-skill-portability.md))と衝突する。

### 文書ごとに別の観点を持つ

**同じ項目を複数の文書で繰り返しチェックさせない**。重複はそれ自体が形骸化の原因になる。

| 文書 | check | 問うこと | 確認者 |
|---|---|---|---|
| `research` | `source_quality` | 出典・鮮度・数値の転記精度 | consultant |
| `as-is-report` | `reality_gap` | 公開情報から見える姿を現場実態と突き合わせたか | consultant → customer |
| | `past_attempts` | その課題にこれまで取り組んだか、なぜ進まなかったか | consultant → customer |
| | `hidden_stakeholders` | 影響を受ける人・承認が必要な人が他にいないか | consultant → customer |
| | `decision_maker` | 決裁権限を持つのは誰か | consultant → customer |
| | `internal_consistency` | **前回版と矛盾していないか。制約と両立するか** | consultant |
| | `as_is_articulation` | **現状認識は合っているか。語られていない実態はないか** | customer |
| 討議用スライド | `expression_safety` | リフレーミング規約に反する表現はないか。開示制御は適切か | consultant |
| `to_be` | `to_be_articulation` | **あるべき姿を描けるか。誰の視点のToBeか** | customer |
| | `feasibility` | 制約と両立するか。過渡期は描けているか | consultant → customer |
| 全体 | `scope_agreement` | 今回の対象範囲(`scope: core`)はこれでよいか | customer |

**`reality_gap` の問い方には注意が要る**。標榜していることと現場の実態の乖離を不用意に突くと、組織は自己防衛のために隠蔽・反発に走り対話が閉じる(Argyrisの組織防衛論)。告発・尋問と受け取られない**協調的探索の問い**に変換する。

### 段階的に出す

**初日から全項目を並べない**。探索の初期に全チェックが並ぶと「全部埋めないと動かない」という圧を与え、[status契約](phase2-status-contract.md)の段階的開示と衝突する。

| 段階 | 出す check |
|---|---|
| `discovery`(`to_be` が0件) | `source_quality` / `reality_gap` / `past_attempts` / `hidden_stakeholders` / `as_is_articulation` |
| `convergence` | 上記 + `internal_consistency` / `expression_safety` / `to_be_articulation` / `feasibility` / `decision_maker` / `scope_agreement` |

### 「判断できない」を第一級の状態にする

**チェックリストで判断できない場合はありうる。そして、判断できないこと自体が課題であることもある。**

顧客が「あるべき姿を語れない」とき、それは埋めるべき欠落とは限らない。「組織として方向性が定まっていない」「部門間で前提が食い違っている」「そもそも誰も考えていない」といった**発見であり、案件の核心的な課題**でありうる。

```
result: completed | finding | undeterminable
```

| result | 意味 |
|---|---|
| (イベント無し) | 未確認 |
| `completed` | 確認した。特筆すべきものは無い |
| `finding` | 確認して**何かが見つかった**。`note` または `finding_refs` を必須とする |
| **`undeterminable`** | **確認したが判断できなかった**。`note` に理由を必須で記録する |

**中立的な語彙にする**(Codex指摘による訂正)。当初案の `confirmed_none` / `identified` は「探索対象の有無」には使えるが、品質・合意・安全性の評価には意味が定まらなかった — `source_quality=identified` が「良質な出典を確認した」なのか「品質問題を発見した」なのか判別できない。`completed` / `finding` なら11項目すべてで意味が一貫する。

`undeterminable` は**欠落ではなく発見**として扱う。ただし**無条件に充足として数えない**。

#### 判断不能には「扱いを決める」ことを求める

**すべてを `undeterminable` と記録すれば収束できてしまう抜け道を塞ぐ**(agy指摘)。「寛容さはプロセスの層に」(不変条件7)が、検証そのものの骨抜きに変質してはならない。

```python
disposition: Literal["open", "deferred", "promoted"] = "open"
```

`CheckRecorded(result="undeterminable")` に `disposition` を持たせ、その後の扱いを記録する。

| disposition | 意味 | 収束への影響 |
|---|---|---|
| `open` | まだ扱いを決めていない | **収束をブロックする** |
| `deferred` | 今回は不問・保留と判断した | ブロックしない |
| `promoted` | 課題または未確定事項へ昇格させた | ブロックしない |

**核となる2項目は `deferred` を許さない**。`reality_gap` と `decision_maker` は、判断できないまま先へ進むと提案の土台が崩れる。この2項目は `promoted` へ昇格させることでのみ先へ進める。

これにより、判断不能が残っていても**扱いを決めれば前へ進める**一方、扱いを決めずに素通りすることはできない。

### 未確定・矛盾・判断不能は課題の候補である

`undeterminable` と `Gap(kind="internal_conflict")` は、そのままでは打ち手のパイプラインに流れない。しかし**それ自体が解くべき課題である**と判断したときに、`challenge` へ昇格できる。

```python
class Challenge(ScopedNode):
    ...
    promoted_from: str = ""   # 昇格元(gap-N / ev-N)
```

当初案は `internal_conflict` に「パイプラインに直接流さない」と書いて経路を塞いでいた。**論理矛盾やトレードオフが課題であることもある**ため、この判断を撤回する。昇格は自動ではなく、人間が判断したときに記録する。

#### 昇格先は Challenge だけではない

**すべてを課題にすると一覧が肥大化する**(agy指摘)。些細な認識相違や単なる情報不足まで課題化すると、本当に解くべきことが埋もれる。次の基準で仕分ける。

| 昇格先 | 基準 |
|---|---|
| `Challenge`(解くべき問い) | ①ゴール達成に直結する ②構造的なトレードオフで意思決定が要る ③`cost_of_inaction` を定義できる — **これらを満たす場合** |
| `OpenQuestion`(共に解明する問い) | 解明が要るが、まだ「解くべき課題」と断定できない |
| `Constraint`(制約) | 変えられない前提として受け入れる |
| (昇格しない) | 上記のいずれでもない。`disposition: deferred` で保留する |

#### 顧客に向けては「課題」と呼ばない

**「答えられないこと自体が御社の課題です」と伝えるのは危険である**(agy指摘)。顧客が語れない理由の多くは情報不足・社内利害の未調整・語彙の欠如であり、そこを課題と名指しすると組織防衛を激しく刺激し、伴走ではなく**査定・責任転嫁**と受け取られて信頼が壊れる。

- **内部の扱い**: `Challenge` として構造化し、真因分析のパイプラインに載せる
- **顧客への提示**: 「**共に解明したい問い**」として提示する。討議用スライドでは `OpenQuestion` の語彙を使う

同じ実体を、内部では課題として扱い、対話では共同探求の問いとして扱う。これはリフレーミング規約([スライド設計](phase2-slides-design.md))と同じ考え方である。

昇格の記録により、「なぜこれが課題なのか」を矛盾の発見まで遡って追跡できる。

### check registry: 有効期間と適用条件

**checkには「いつまで有効か」がある**(Codex指摘)。当初案は「要件が更新されても check は自動的に無効化しない」としていたが、これでは**内容が変わっても旧結果が通り続ける**。特に `internal_consistency` や `feasibility` は、要件が変われば再確認が要る。

CLIが持つ registry で、項目ごとに次を定義する。

| check | 種別 | 対象 | 再確認を要求する変更 |
|---|---|---|---|
| `source_quality` | artifact束縛 | `research` | 対象の再生成 |
| `reality_gap` | 持続 | requirements | — |
| `past_attempts` | 持続 | requirements | — |
| `hidden_stakeholders` | 持続 | requirements | — |
| `decision_maker` | 持続 | requirements | `stakeholders` の変更 |
| `internal_consistency` | 版束縛 | requirements | 論理連鎖の中核ノードの `substantive` 変更 |
| `as_is_articulation` | artifact束縛 | `as-is-report` | 対象の再生成 |
| `expression_safety` | artifact束縛 | 討議用 `slides` | 対象の再生成 |
| `to_be_articulation` | 版束縛 | requirements | `to_be` の `substantive` 変更 |
| `feasibility` | 版束縛 | requirements | `to_be` / `constraints` の `substantive` 変更 |
| `scope_agreement` | 版束縛 | requirements | `scope` の変更 |

- **持続**: 一度記録すれば有効。要件更新で無効化しない
- **版束縛**: 上表の変更があった時点で失効し、再確認が必要になる
- **artifact束縛**: 対象の生成物が再生成されたら失効する。畳み込みは反応と同じく**対象の系列ごと**に行う

> **有効なcheckの決定**: 現在の対象に適用される check それぞれについて、失効していない最新の `CheckRecorded` を有効値とする。

### `finding` に対応するレコード

整合検証に使う。対応レコードを定義できない check は検証対象外とする。

| check | `finding` が意味するもの |
|---|---|
| `reality_gap` | `Gap(kind="perception")` が1件以上 |
| `past_attempts` | `Attempt` が1件以上(`outcome` は問わない) |
| `hidden_stakeholders` | `Stakeholder(surfaced_by="inferred")` が1件以上 |
| `decision_maker` | `Stakeholder(is_decision_maker=True)` が1件以上 |
| その他 | `finding_refs` または `note` が非空であることのみ検証する |

`finding` なのに対応レコードが0件、または `completed` なのに対応レコードが存在する場合は**不整合**として報告する。

**`inconsistent` が残っていても `readiness` は通す**。不整合は報告であって強制ではない(不変条件6)。

### チェックリスト自体の形骸化を検出する

**要件に `substantive` な変更があったにもかかわらず、同じ check の有効値が3周続けて `completed` だったら報告する**。判定は `workflow.checks.ritualized` に出す。

変更が無い周回を数に入れない(agy指摘)。ステークホルダーが最初から限定されている案件では `hidden_stakeholders` が `completed` のまま続くのが正常であり、単純な連続回数では誤検出になる。

これは私(medoの設計者)が改訂のたびに矛盾を混入させた問題と同じ構造である — **チェックする側が機能しているかを、別の層が見る必要がある**。報告であって強制ではない。

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
| 3 | その段階で出る check(§6)がすべて記録されている。`undeterminable` は `disposition` が `deferred` / `promoted` なら充足として数える | `check_missing` / `undeterminable_open` |
| 4 | 未解決の `changes_requested` が無い | `review_findings_open` |
| 5 | 決裁者(`is_decision_maker=True`)から `purpose="to_be_go_ahead"` の `agreed` が得られている | `to_be_go_ahead_missing` |
| 6 | `influence="high"` のステークホルダーに、有効値としての `objected` が残っていない | `high_influence_objection_open` |

**標準周回の出口は `to_be_go_ahead` であり、`phase_signoff` ではない**(agy指摘による訂正)。当初案は収束条件に決裁者の `phase_signoff`(フェーズ完了承認)を要求していたが、**この段階では打ち手も費用感も体制も提示していない**。解決策が無い状態で決裁者が次期投資の正式サインオフを出すことは実務上あり得ず、`decision_maker_signoff_missing` で永久に不合格になり、後続の `propose-options` へ進めなくなる。

| ゲート | 判定 | 必要な承認 | いつ |
|---|---|---|---|
| **標準周回の収束**(本表) | `readiness.state = "ready"` | `to_be_go_ahead` の `agreed` | 現状と理想が合意でき、打ち手の検討に進んでよい |
| **フェーズ完了** | `phase_readiness`(下記) | `phase_signoff` の `agreed` | 最終提案スライド(Ask)を提示した後 |

### phase_readiness

**`phase_signoff` の target は最終提案スライドの生成物とする**(`requirements` ではない)。要件版を対象にすると、同じ要件版から `prfaq` や最終提案スライドを再生成しても古い承認が有効なまま残る。**何を見て承認したか**が一意に定まる必要がある。

| purpose | 許容する target(§3の表を更新) |
|---|---|
| `phase_signoff` | `artifact`(`slides` の `slide_kind="final"` のみ) |

```json
"phase_readiness": {
  "state": "ready | not_ready | not_evaluable",
  "failed_conditions": [{"code": "...", "refs": []}]
}
```

| # | 条件 | 理由コード |
|---|---|---|
| 1 | 標準周回の `readiness.state == "ready"` | `convergence_not_ready` |
| 2 | `prfaq` が存在し stale でない | `prfaq_missing_or_stale` |
| 3 | `slide_kind="final"` の `slides` が存在し stale でない | `final_slides_missing_or_stale` |
| 4 | 決裁者から**現在の**最終提案スライドに対する `phase_signoff` の `agreed` | `phase_signoff_missing` |

`prfaq` が存在しない段階では `not_evaluable` を返す(標準周回のみを回している間は評価しない)。

**条件4は祖先からの継承を認めない**。他のpurposeと違い、最終提案スライドを作り直したら旧スライドへの承認は無効になる。承認は「何を見て決めたか」と不可分であり、資料が変われば同じ承認とは言えない。畳み込みは `EffectiveResponse.on_current_target` でこれを表す。

**条件2の「裏づけ済み」の判定式**: ToBeと内部実態を結ぶ経路を既存の `Gap(kind="goal")` で定義する。

> **ToBe `tb-N` が裏づけを持つ** ⟺ `from_to_be` に `tb-N` を含む `Gap(kind="goal")` が存在し、その `from_as_is` に `visibility="internal"` かつ `confidence != "open"` の AsIs が1件以上含まれる

**`undeterminable` それ自体は不合格にしない**。「確認したが判断できなかった」は確認プロセスが機能した結果であり、未実施とは違う。ただし**扱いを決めないまま(`disposition: open`)は収束させない** — でなければ全項目を判断不能と記録して素通りできてしまう(§6)。

**条件5・6が収束判断の中核である**。単なる頭数では判定しない — 現場担当者2名の共感で通る一方、決裁者が未確認でも通り、影響力の無い1名の異議で全体が止まる、という誤判定を防ぐ。

**これは保存ゲートではなく診断である**。条件を満たさなくてもPRFAQやスライドの生成は妨げない。

### 周回の成果を示す

**回るほど疑われる構造にしない**。当初案は `round_count`(何周したか)と `divergence_warning`(3周超えたら発散疑い)しか持たず、**ループを回すこと自体が疑いの対象**になっていた。

往復は暗黙知を引き出す機構であり、**回ること自体が価値**である。周回ごとに何が得られたかを返す。

```json
"round_delta": {
  "new_internal_as_is": 2,
  "new_constraints": 1,
  "resolved_objections": 1,
  "promoted_challenges": 1,
  "confidence_raised": ["tb-1"],
  "undeterminable_found": ["to_be_articulation"]
}
```

`undeterminable_found` も**成果として数える**。「顧客があるべき姿を語れないと分かった」ことは前進であり、次に何を掘るかを決める材料になる。

**各項目は `round_id` で帰属を決める**。全イベントが envelope に `round_id` を持ち(§2)、要件変更は変更manifestの版を `round_count` アルゴリズムに通して周回を決める。

| 項目 | 算出 |
|---|---|
| `new_internal_as_is` | その周回の要件版で新規追加された `visibility="internal"` の AsIs 件数 |
| `new_constraints` | 同上、`constraints` の新規追加件数 |
| `resolved_objections` | その `round_id` のイベントで有効値から外れた `objected` の件数 |
| `promoted_challenges` | その周回の要件版で `promoted_from` が新規に設定された `challenge` の件数 |
| `confidence_raised` | その周回で `confidence` が上がったノードのID |
| `undeterminable_found` | その `round_id` で**初めて** `undeterminable` になった check 名。**2周以上続けて同じ項目が判断不能のままなら数えない** |

`progress_count` を上記の合計(IDリストは件数に換算)として定義する。

**同じ項目の判断不能が続く場合を成果に数えない**(agy指摘)。毎周「やはり判断できませんでした」を記録するだけで `progress_count` が非ゼロになり、**進捗のない空転が発散警告に引っかからなくなる**ためである。初回の発見は前進だが、繰り返しは停滞である。

### 往復の発散

**直近2周の `progress_count` がいずれも0**の状態を **発散の疑い**として報告する。新たに得られるものが2周続けて無いことを意味する。論点の発散、ステークホルダー間の対立、スコープ肥大化の兆候になる。実務上の有効な往復は2〜3周が目安である。

**これは失敗の警告ではなく、論点を絞る合図である**。`focus_hypothesis` を絞り直すか、`scope` を `secondary` へ移す判断の材料になる。停止条件ではない。

**収束の目安**: 新規に得られた実態によってToBeの修正差分が出なくなった状態(飽和)。

### round_count の算出

要件バージョンの履歴を古い順に走査し、**`as_is` が変更された版のあと `to_be` が変更された版が現れたら1周とカウントする**。

```
round = 0
state = "waiting_as_is"
各版 v を古い順に:
    as_is変更 = manifest.changed_sections に "as_is" を含む
    to_be変更 = manifest.changed_sections に "to_be" を含む
    if state == "waiting_as_is" and as_is変更:
        state = "waiting_to_be"
    if state == "waiting_to_be" and to_be変更:
        round += 1
        state = "waiting_as_is"
```

**同一の保存で `as_is` と `to_be` の両方が変わった場合は1周と数える**(`waiting_as_is` から入って同じ版で `to_be` 変更も成立するため)。`change_kind: "editorial"` の版は走査から除外する。

`round_id` は全イベントの envelope に記録され、`round_count` はその最大値と一致する。

発散の報告は**停止条件ではない**。
