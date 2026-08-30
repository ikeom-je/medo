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
```

`TargetRef` を判別共用体にすることで、`target_kind` と `target_id` / `target_version` の排他制約がスキーマで保証される。

### 5つのイベント型

```python
class DiscoveryCheckRecorded(WorkflowEventBase):
    kind: Literal["discovery_check"] = "discovery_check"
    check: Literal["reality_gap", "past_attempts", "hidden_stakeholders", "decision_maker"]
    result: Literal["confirmed_none", "identified"]

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
    round_id: int                          # この節目が属する周回
    focus_hypothesis_id: str = ""          # この周回で検証する論点(任意)

class ToBeCheckpointRecorded(WorkflowEventBase):
    kind: Literal["tobe_checkpoint"] = "tobe_checkpoint"
    answer: Literal["generate", "defer"]
    responds_to: str                       # 回答対象の MilestoneDetected のイベントID
```

**節目の検出自体をイベントにする**。当初案は `ToBeCheckpointRecorded` が回答しか持たないのに「同イベントの未回答状態が立つ」と説明しており、**未回答状態がどのデータから導かれるのかが定義できていなかった**。節目を `MilestoneDetected` として記録し、回答を `responds_to` で紐づけることで、未回答は「対応する `ToBeCheckpointRecorded` を持たない `MilestoneDetected`」として一意に導ける。

`round_id` と `focus_hypothesis_id` も `MilestoneDetected` が持つ。当初案は索引で `focus_hypothesis_id` に言及しながら保存先が無く、envelope に周回が付くと書きながら周回IDが無かった。

**`round_id` の採番**: `MilestoneDetected` を記録する時点で、§7 の `round_count` アルゴリズムを最新の要件履歴に適用して得た値を入れる。周回が進んでいなければ直前の `MilestoneDetected` と同じ値になる。これにより `round_count` と `max(round_id)` が一致する。

**`focus_hypothesis_id` の設定**: `medo checkpoint answer --focus <hyp-id>` で指定する。指定が無ければ直前の `MilestoneDetected` の値を引き継ぐ(周回をまたぐまで同じ論点を追う)。参照先が実在する仮説であることを保存時に検証する。

**保存時の検証**: `ToBeCheckpointRecorded.responds_to` が実在する `MilestoneDetected` のIDであり、まだ回答されていないこと(二重回答を防ぐ)。

**記録の冪等性**: 要件保存とイベント記録は別ストアであるため、要件保存後に `MilestoneDetected` の記録が失敗する可能性がある。**`(requirements_version, condition)` の組で重複を排除する** — 同じ版の同じ条件に対する `MilestoneDetected` は1件しか作らない。再試行しても重複しない。

### イベント型ごとの許容target

判別共用体だけでは、すべてのイベントが両方のtargetを取れてしまう。**型ごとに固定する**。

| イベント型 | 許容する target |
|---|---|
| `DiscoveryCheckRecorded` | `requirements` |
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

## 6. 発見プロセスの確認

AsIsに暗黙知が入らないままToBeを確定させると理想の正論に終わる。これを防ぐ**4つの確認**をSkillの契約とする。実施結果は `DiscoveryCheckRecorded` イベントに記録する。

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

**同じ check が複数回記録された場合は、`id` の採番順で最後のものを有効値とする**(反応の畳み込みと同じ規則)。要件が更新されても check は自動的に無効化しない — 実施した事実は残る。

**`inconsistent` が残っていても `readiness` は通す**。不整合は報告であって強制ではない(不変条件6)。`readiness.failed_conditions` には含めず、`workflow.checks.inconsistent` に列挙するに留める。

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
| 4 | 決裁者から最新の最終提案スライドに対する `phase_signoff` の `agreed` | `phase_signoff_missing` |

`prfaq` が存在しない段階では `not_evaluable` を返す(標準周回のみを回している間は評価しない)。

**条件2の「裏づけ済み」の判定式**: ToBeと内部実態を結ぶ経路を既存の `Gap(kind="goal")` で定義する。

> **ToBe `tb-N` が裏づけを持つ** ⟺ `from_to_be` に `tb-N` を含む `Gap(kind="goal")` が存在し、その `from_as_is` に `visibility="internal"` かつ `confidence != "open"` の AsIs が1件以上含まれる

**条件5・6が収束判断の中核である**。単なる頭数では判定しない — 現場担当者2名の共感で通る一方、決裁者が未確認でも通り、影響力の無い1名の異議で全体が止まる、という誤判定を防ぐ。

**これは保存ゲートではなく診断である**。条件を満たさなくてもPRFAQやスライドの生成は妨げない。

### 往復の発散

`round_count` が3を超えても `to_be` の `confirmed` が増えない状態を **発散の疑い**として報告する。論点の発散、ステークホルダー間の対立、スコープ肥大化の兆候になる。実務上の有効な往復は2〜3周が目安である。

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

`round_id` は `MilestoneDetected` に記録され、`round_count` はその最大値としても導ける(両者は一致する)。

発散の報告は**停止条件ではない**。
