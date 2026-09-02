# フェーズ2 決定論層 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 上流工程の標準周回(調べる→内部検証→ぶつける→振り返る)を回すために必要な、案件内容・進行記録・診断のすべてを `medo` CLI が決定論的に保存・返却できるようにする。

**Architecture:** 3層に分ける。(1) `RequirementsDoc` が案件内容の正本を持ち、ID採番簿と変更manifestが版間の追跡を担う。(2) `WorkflowEvent` が進行記録を要件とは独立した追記型ストアに持つ。(3) `status` が両者を読んで診断を合成する。LLMは一切呼ばない。

**Tech Stack:** Python 3.12+ / pydantic v2 / typer / pytest / uv workspace(core・cli)

## Global Constraints

- 対象範囲は[フェーズ2設計の実装順序](../specs/medo-phase2-design.md#5-フェーズ2の実装順序)の**優先度1〜4**。優先度5〜6(Skill本文・スライド生成)は別計画
- **数値・事実の通り道にLLMを挟まない**。core は宣言(`change_kind` 等)を決定論的に処理するだけで、本文の意味差を推測しない
- **診断は報告であって強制ではない**。未接続・未確認・未解決を検出しても保存を拒否しない。保存を拒否するのは**スキーマ違反と参照整合性違反のみ**
- ストレージパスはFirestore互換(document=偶数セグメント、collection=奇数セグメント)
- リント: ruff line-length 100。テスト: `uv run pytest` / `uv run ruff check .` が両方通ることがコミットの絶対条件
- 日付を扱う関数は `today: date` を引数で受け取る(テストで固定するため `date.today()` を関数内で直接呼ばない)
- 新規ファイルは `core/src/medo_core/<name>.py` + `core/tests/test_<name>.py` に置く
- 既存の公開API(`RequirementsStore.save/get/diff` / `ArtifactStore.save/get/list` / `project_status`)のシグネチャは、本計画で明示的に変更するもの以外は壊さない

## 設計正本

| 内容 | 参照 |
|---|---|
| ノード・ID規約・変更manifest | [phase2-domain-model.md](../specs/phase2-domain-model.md) |
| イベント・収束規則・チェックリスト | [phase2-workflow-model.md](../specs/phase2-workflow-model.md) |
| 診断のJSON契約・actions優先順位 | [phase2-status-contract.md](../specs/phase2-status-contract.md) |
| 生成物の依存・陳腐化・カバレッジ | [phase2-artifact-lifecycle.md](../specs/phase2-artifact-lifecycle.md) |

## ファイル構成

| ファイル | 責務 |
|---|---|
| `core/src/medo_core/nodes.py` | **新規**。`Node` / `ScopedNode` と全ノード型(`AsIs`〜`Hypothesis`)。永続化を持たない純粋なスキーマ |
| `core/src/medo_core/requirements.py` | 既存を拡張。`RequirementsDoc` / `RequirementsStore`(採番・検証・manifest保存) |
| `core/src/medo_core/manifest.py` | **新規**。`ChangeManifest` / `SectionChange` / セクション差分の算出 |
| `core/src/medo_core/events.py` | **新規**。5つのイベント型 / `EventStore` / 畳み込み |
| `core/src/medo_core/checks.py` | **新規**。check registry(有効期間・適用条件・段階) |
| `core/src/medo_core/artifacts.py` | 既存を拡張。`derived_from` / `slide_kind` / セクション依存 / stale伝播 |
| `core/src/medo_core/watermark.py` | **新規**。ID採番簿(プレフィックス別 high-water mark) |
| `core/src/medo_core/workflow.py` | **新規**。イベント記録の入口。他ストアを参照する検証と節目の自動記録 |
| `core/src/medo_core/responses.py` | **新規**。収束対象の解決と反応の畳み込み |
| `core/src/medo_core/diagnostics.py` | **新規**。model診断・収束判定・周回成果 |
| `core/src/medo_core/context.py` | **新規**。診断素材の収集と workflow 枝の組み立て |
| `core/src/medo_core/status.py` | 既存を拡張。4階層の提示と actions 合成。**フェーズ1の `next_step` ロジックは変更しない** |
| `cli/src/medo_cli/main.py` | 既存を拡張。肥大化するため `commands/` へ分割する(Task 20) |
| `cli/src/medo_cli/commands/workflow.py` | **新規**。進行記録の4コマンド。`main.py` を import しない |
| `cli/src/medo_cli/trace.py` | **新規**。CLI呼び出し列の記録(Skill再現性のホスト間比較) |

**`nodes.py` を `requirements.py` から分離する理由**: ノード型は `events.py`(`promoted_from` の検証)と `status.py`(診断)からも参照される。`requirements.py` に置くと `Store` の実装まで巻き込んだ循環参照になる。

---

## Task 1: ノード基底とID採番簿

**Files:**
- Create: `core/src/medo_core/nodes.py`
- Create: `core/tests/test_nodes.py`
- Create: `core/src/medo_core/watermark.py`
- Create: `core/tests/test_watermark.py`

**Interfaces:**
- Produces: `Confidence` / `Scope` 型エイリアス、`Node(id, text, confidence, evidence_refs)`、`ScopedNode(Node, scope)`、`IdWatermark.allocate(prefix, count) -> list[str]`、`IdWatermarkStore.load(project_id) -> IdWatermark` / `.save(project_id, wm)`

- [ ] **Step 1: `nodes.py` の基底を書く**

```python
"""案件内容のノード型。永続化を持たない純粋なスキーマ。

要件・イベント・診断のすべてが参照するため、Storeを持つモジュールから分離する
(requirements.py に置くと events.py との循環参照になる)。
"""

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["confirmed", "assumed", "open"]
Scope = Literal["core", "secondary", "out"]


class Node(BaseModel):
    """IDを持つ案件内容の最小単位。

    id が空文字なら保存時に core が採番する。
    """

    id: str = ""
    text: str
    confidence: Confidence = "open"
    evidence_refs: list[str] = Field(default_factory=list)


class ScopedNode(Node):
    """診断のスコープ絞り込み対象になるノード。

    案件の属性(Kpi / Stakeholder)には scope を付けない。
    """

    scope: Scope = "core"
```

- [ ] **Step 2: 採番簿のテストを書く**

`core/tests/test_watermark.py`:

```python
from medo_core.storage import LocalJsonStorage
from medo_core.watermark import IdWatermark, IdWatermarkStore


def test_allocate_returns_sequential_ids_for_prefix():
    wm = IdWatermark()

    assert wm.allocate("as", 3) == ["as-1", "as-2", "as-3"]


def test_allocate_continues_from_previous_high_water_mark():
    wm = IdWatermark(marks={"as": 5})

    assert wm.allocate("as", 2) == ["as-6", "as-7"]


def test_allocate_does_not_reuse_id_of_deleted_node(tmp_path):
    store = IdWatermarkStore(LocalJsonStorage(tmp_path))
    wm = store.load("p1")
    wm.allocate("as", 3)
    store.save("p1", wm)

    reloaded = store.load("p1")

    assert reloaded.allocate("as", 1) == ["as-4"]


def test_prefixes_are_numbered_independently():
    wm = IdWatermark()
    wm.allocate("as", 2)

    assert wm.allocate("tb", 1) == ["tb-1"]


def test_load_returns_empty_watermark_for_unknown_project(tmp_path):
    store = IdWatermarkStore(LocalJsonStorage(tmp_path))

    assert store.load("unknown").marks == {}
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_watermark.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_core.watermark'`

- [ ] **Step 4: `watermark.py` を実装**

```python
"""ID採番簿。プレフィックス別の high-water mark を単調増加で保持する。

直前バージョンの最大ID+1で採番すると、最大IDのノードを削除した後に
そのIDを再利用してしまう。採番簿を永続化してこれを防ぐ。

load → allocate → save はトランザクションではない。並行保存が起きると同じIDを
二重に割り当てうる。利用スコープが本人のみで同時保存が起きない前提に依存している。
"""

from pydantic import BaseModel, Field

from medo_core.storage import Storage


class IdWatermark(BaseModel):
    marks: dict[str, int] = Field(default_factory=dict)

    def allocate(self, prefix: str, count: int) -> list[str]:
        """prefix の採番を count 件進め、割り当てたIDを返す。"""
        start = self.marks.get(prefix, 0)
        ids = [f"{prefix}-{n}" for n in range(start + 1, start + count + 1)]
        self.marks[prefix] = start + count
        return ids


class IdWatermarkStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _path(self, project_id: str) -> str:
        return f"projects/{project_id}/meta/id_watermark"

    def load(self, project_id: str) -> IdWatermark:
        raw = self._storage.get(self._path(project_id))
        return IdWatermark.model_validate(raw) if raw else IdWatermark()

    def save(self, project_id: str, watermark: IdWatermark) -> None:
        self._storage.put(self._path(project_id), watermark.model_dump(mode="json"))
```

**Firestoreでの並行保存はこの実装では保護されない**。設計正本は採番簿の更新をトランザクションで行うと定めているが、`Storage` プロトコルに `transact` が無く、追加すると `LocalJsonStorage` にも実装が要る。**利用スコープが本人のみ(不変条件5)で同時保存が起きないため、本計画では対応しない**。モジュールのdocstringにこの制約を明記し、[範囲外](#本計画の範囲外)に記録する。

- [ ] **Step 5: ノード基底のテストを書く**

`core/tests/test_nodes.py`:

```python
from medo_core.nodes import Node, ScopedNode


def test_node_defaults_to_open_confidence_and_empty_id():
    node = Node(text="現状は手作業")

    assert node.id == ""
    assert node.confidence == "open"
    assert node.evidence_refs == []


def test_scoped_node_defaults_to_core_scope():
    node = ScopedNode(text="現状は手作業")

    assert node.scope == "core"
```

- [ ] **Step 6: テストが両方通ることを確認**

Run: `uv run pytest core/tests/test_nodes.py core/tests/test_watermark.py -v`
Expected: 7 passed

- [ ] **Step 7: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/nodes.py core/src/medo_core/watermark.py core/tests/test_nodes.py core/tests/test_watermark.py
git commit -m "feat(core): ノード基底とID採番簿を追加

削除済みIDの再利用を防ぐため、直前バージョンからの最大値+1ではなく
プレフィックス別のhigh-water markを永続化する。"
```

---

## Task 2: 論理連鎖のノード型と参照整合性

**Files:**
- Modify: `core/src/medo_core/nodes.py`
- Modify: `core/tests/test_nodes.py`

**Interfaces:**
- Consumes: Task 1 の `Node` / `ScopedNode` / `Confidence` / `Scope`
- Produces: `AsIs` / `ToBe` / `Gap` / `Bottleneck` / `Challenge` / `Constraint` / `OpenQuestion` / `PromotionSource`、およびプレフィックス表 `ID_PREFIXES: dict[str, str]`(セクション名 → プレフィックス)

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_nodes.py` に追記:

```python
import pytest
from pydantic import ValidationError

from medo_core.nodes import (
    ID_PREFIXES,
    AsIs,
    Bottleneck,
    Challenge,
    Gap,
    PromotionSource,
    ToBe,
)


def test_as_is_requires_explicit_visibility():
    """既定値を持たせると、指定漏れの公開情報が内部実態として扱われ
    認識GAPの検出が壊れる。"""
    with pytest.raises(ValidationError):
        AsIs(text="紙の伝票を手入力している")


def test_as_is_records_reality_checked_separately_from_gap():
    node = AsIs(text="DX推進中と公表", visibility="public", reality_checked=True)

    assert node.reality_checked is True


def test_to_be_holds_business_journey_before_and_after():
    """抽象的な状態記述だけでは顧客が訂正できないため、具体シナリオを持つ。"""
    node = ToBe(
        text="伝票処理が自動化されている",
        journey_before="朝9時に担当者が紙の伝票を手入力する",
        journey_after="朝9時にシステムが取り込み、担当者は例外のみ確認する",
    )

    assert node.journey_before.startswith("朝9時")


def test_gap_defaults_to_goal_kind():
    assert Gap(text="乖離がある").kind == "goal"


def test_bottleneck_records_promoting_hypothesis():
    node = Bottleneck(text="承認が3階層ある", confidence="confirmed", from_hypothesis="hyp-1")

    assert node.from_hypothesis == "hyp-1"


def test_challenge_can_record_promotion_source_as_typed_value():
    """生の文字列だと任意のイベントからでも昇格扱いにできてしまう。"""
    node = Challenge(
        text="どちらの実態を前提にするか",
        promoted_from=PromotionSource(kind="internal_conflict", ref="gap-3"),
    )

    assert node.promoted_from.kind == "internal_conflict"


def test_id_prefixes_cover_every_numbered_section():
    assert ID_PREFIXES["as_is"] == "as"
    assert ID_PREFIXES["to_be"] == "tb"
    assert set(ID_PREFIXES) == {
        "as_is", "to_be", "kpis", "stakeholders", "gaps", "bottlenecks",
        "challenges", "constraints", "attempts", "hypotheses", "open_questions",
    }
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_nodes.py -v`
Expected: FAIL — `ImportError: cannot import name 'AsIs'`

- [ ] **Step 3: ノード型を実装**

`core/src/medo_core/nodes.py` に追記:

```python
class PromotionSource(BaseModel):
    """課題の昇格元。矛盾・判断不能が「解くべき課題」になった経緯を残す。"""

    kind: Literal["internal_conflict", "undeterminable"]
    ref: str  # gap-N(internal_conflict) または ev-N(undeterminable)


class AsIs(ScopedNode):
    visibility: Literal["public", "internal"]
    source_stakeholder_ids: list[str] = Field(default_factory=list)
    reality_checked: bool = False


class ToBe(ScopedNode):
    evidenced_by: list[str] = Field(default_factory=list)
    assumed_risks: list[str] = Field(default_factory=list)
    transition_steps: list[str] = Field(default_factory=list)
    journey_before: str = ""
    journey_after: str = ""


class Gap(ScopedNode):
    kind: Literal["perception", "internal_conflict", "goal"] = "goal"
    from_as_is: list[str] = Field(default_factory=list)
    from_to_be: list[str] = Field(default_factory=list)


class Bottleneck(ScopedNode):
    gap_ids: list[str] = Field(default_factory=list)
    from_hypothesis: str = ""


class Challenge(ScopedNode):
    bottleneck_ids: list[str] = Field(default_factory=list)
    cause_hypothesis_ids: list[str] = Field(default_factory=list)
    cost_of_inaction: str = ""
    promoted_from: PromotionSource | None = None


class Constraint(ScopedNode):
    """予算・期間・体制・法令・既存システム。"""


class OpenQuestion(ScopedNode):
    """未確定事項。レビュー所見から参照されるためIDを持つ。"""


ID_PREFIXES = {
    "as_is": "as",
    "to_be": "tb",
    "kpis": "kpi",
    "stakeholders": "sh",
    "gaps": "gap",
    "bottlenecks": "bn",
    "challenges": "ch",
    "constraints": "cs",
    "attempts": "at",
    "hypotheses": "hyp",
    "open_questions": "oq",
}
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_nodes.py -v`
Expected: 9 passed

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/nodes.py core/tests/test_nodes.py
git commit -m "feat(core): 論理連鎖のノード型を追加

AsIs.visibility を必須にする。既定値を持たせると指定漏れの公開情報が
内部実態として扱われ、認識GAPの検出が成立しなくなる。"
```

---

## Task 3: 属性ノード(KPI・ステークホルダー・既往の取り組み・仮説)

**Files:**
- Modify: `core/src/medo_core/nodes.py`
- Modify: `core/tests/test_nodes.py`

**Interfaces:**
- Consumes: Task 1 の `Node`、Task 2 の型群
- Produces: `Kpi` / `Stakeholder` / `Attempt` / `Hypothesis` / `FermiRef` / `BlockerCategory`

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_nodes.py` に追記:

```python
from medo_core.nodes import Attempt, FermiRef, Hypothesis, Kpi, Stakeholder


def test_kpi_holds_current_value_as_fact_reference_not_number():
    """現状値は観測された事実。数値の通り道にLLMを挟まないため fact を参照する。"""
    kpi = Kpi(text="受注リードタイム", name="lead_time", current_fact_id="fact-3",
              target_value=2.0, unit="日")

    assert kpi.current_fact_id == "fact-3"
    assert not hasattr(kpi, "current_value")


def test_kpi_has_no_scope_attribute():
    """scope は作業対象ノードだけが持つ。案件の属性には適用しない。"""
    assert "scope" not in Kpi.model_fields


def test_stakeholder_separates_influence_from_decision_authority():
    """案件を頓挫させるのは「決裁権はないが拒否権を持つ実力者」。"""
    sh = Stakeholder(text="情報システム部長", is_decision_maker=False, influence="high")

    assert sh.is_decision_maker is False
    assert sh.influence == "high"


def test_stakeholder_defaults_to_stated_discovery_path():
    assert Stakeholder(text="現場担当").surfaced_by == "stated"


def test_attempt_distinguishes_not_attempted_from_unknown():
    """「取り組んでいない」という確認済みの事実と、未確認の空欄を区別する。"""
    attempt = Attempt(description="検討したことがない", outcome="not_attempted")

    assert attempt.outcome == "not_attempted"


def test_attempt_requires_blocker_when_stalled():
    """頓挫理由は制約とボトルネックの最有力の発見源。"""
    with pytest.raises(ValidationError):
        Attempt(description="RPA導入を試みた", outcome="stalled")


def test_attempt_requires_blocker_when_failed():
    with pytest.raises(ValidationError):
        Attempt(description="RPA導入を試みた", outcome="failed")


def test_attempt_accepts_blocker_category_for_root_cause_direction():
    attempt = Attempt(
        description="RPA導入を試みた",
        outcome="stalled",
        blocker="情報システム部が反対した",
        blocker_category=["politics_incentive"],
    )

    assert attempt.blocker_category == ["politics_incentive"]


def test_hypothesis_connects_impact_to_fermi_variable():
    hyp = Hypothesis(
        kind="impact",
        statement="転記工数が半減する",
        fermi_ref=FermiRef(artifact_id="fermi-v2", variable_name="transcription_hours"),
    )

    assert hyp.fermi_ref.variable_name == "transcription_hours"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_nodes.py -v`
Expected: FAIL — `ImportError: cannot import name 'Kpi'`

- [ ] **Step 3: 実装**

`core/src/medo_core/nodes.py` に追記(`model_validator` は冒頭の pydantic import 行に足す。
モジュール途中の import はリントに掛かる):

```python
class Kpi(Node):
    name: str
    current_fact_id: str = ""
    target_value: float | None = None
    target_text: str = ""
    unit: str = ""
    to_be_ids: list[str] = Field(default_factory=list)


class Stakeholder(Node):
    role: str = ""
    pains: list[str] = Field(default_factory=list)
    stance: Literal["unknown", "supportive", "neutral", "resistant"] = "unknown"
    is_decision_maker: bool = False
    influence: Literal["high", "medium", "low"] = "medium"
    interest: Literal["high", "medium", "low"] = "medium"
    surfaced_by: Literal["stated", "inferred"] = "stated"


BlockerCategory = Literal[
    "resource", "politics_incentive", "technical", "governance", "priority"
]


class Attempt(BaseModel):
    id: str = ""
    challenge_ids: list[str] = Field(default_factory=list)
    gap_ids: list[str] = Field(default_factory=list)
    description: str
    outcome: Literal[
        "not_attempted", "in_progress", "stalled", "failed", "partial", "succeeded"
    ]
    blocker: str = ""
    blocker_category: list[BlockerCategory] = Field(default_factory=list)
    confidence: Confidence = "open"
    evidence_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_blocker_when_not_progressing(self) -> "Attempt":
        if self.outcome in ("stalled", "failed") and not self.blocker:
            raise ValueError(f"outcome={self.outcome} には blocker が必須です")
        return self


class FermiRef(BaseModel):
    artifact_id: str
    variable_name: str


class Hypothesis(BaseModel):
    id: str = ""
    kind: Literal["cause", "solution", "impact"]
    statement: str
    validation_method: str = ""
    status: Literal["unvalidated", "validating", "validated", "rejected"] = "unvalidated"
    evidence_refs: list[str] = Field(default_factory=list)
    challenge_ids: list[str] = Field(default_factory=list)
    fermi_ref: FermiRef | None = None
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_nodes.py -v`
Expected: 18 passed

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/nodes.py core/tests/test_nodes.py
git commit -m "feat(core): KPI・ステークホルダー・既往の取り組み・仮説を追加

KPIの現状値を数値で持たずfactを参照させる。現状値は観測された事実であり、
出典・取得日・stale判定が効く場所に置く必要がある。"
```

---

## Task 4: 変更manifestとセクション差分

**Files:**
- Create: `core/src/medo_core/manifest.py`
- Create: `core/tests/test_manifest.py`

**Interfaces:**
- Consumes: Task 1〜3 のノード型
- Produces: `SectionChange(section, change_kind)` / `ChangeManifest(version, changes, id_only_migration, recorded_on)` / `ManifestStore.save(project_id, m)` / `.list(project_id) -> list[ChangeManifest]` / `changed_sections(old, new) -> list[str]` / `fold_substantive_sections(manifests, from_version) -> set[str]`

**注**: `changed_sections` は `RequirementsDoc` を引数に取るが、`requirements.py` を import すると循環参照になる。**`dict` を受け取る**(`doc.model_dump()` を呼び出し側が渡す)。

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_manifest.py`:

```python
from medo_core.manifest import (
    ChangeManifest,
    ManifestStore,
    SectionChange,
    changed_sections,
    fold_substantive_sections,
    is_text_only_change,
)
from medo_core.storage import LocalJsonStorage


def _doc(**kw) -> dict:
    base = {
        "goal": "",
        "background": "",
        "as_is": [],
        "to_be": [],
        "gaps": [],
        "constraints": [],
        "stakeholders": [],
        "attempts": [],
        "challenges": [],
        "kpis": [],
        "bottlenecks": [],
        "hypotheses": [],
        "open_questions": [],
        "principles": [],
        "functional": [],
        "non_functional": {},
        "sources": [],
        "industry": "",
    }
    base.update(kw)
    return base


def test_first_version_reports_only_filled_sections():
    """初版で空のセクションまで変更扱いにすると、round_countが1周目から
    進んでしまう。"""
    new = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])

    assert changed_sections({}, new) == ["as_is"]


def test_changed_sections_detects_added_node():
    old = _doc()
    new = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])

    assert changed_sections(old, new) == ["as_is"]


def test_changed_sections_detects_text_edit_of_core_node():
    """往復とは本文を精緻化する工程そのもの。軽微と分類すると意味が変わった
    生成物が最新扱いのまま残る。"""
    old = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])
    new = _doc(as_is=[{"id": "as-1", "text": "紙の伝票を手入力", "visibility": "internal"}])

    assert changed_sections(old, new) == ["as_is"]


def test_changed_sections_returns_empty_when_identical():
    doc = _doc(goal="半日で目処を立てる")

    assert changed_sections(doc, doc) == []


def test_changed_sections_reports_each_changed_section():
    old = _doc()
    new = _doc(
        as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}],
        constraints=[{"id": "cs-1", "text": "予算300万円"}],
    )

    assert changed_sections(old, new) == ["as_is", "constraints"]


def test_fold_marks_section_substantive_when_any_version_changed_it():
    manifests = [
        ChangeManifest(version=2, changes=[SectionChange(section="as_is")],
                       recorded_on="2026-08-01"),
        ChangeManifest(version=3, changes=[SectionChange(section="to_be")],
                       recorded_on="2026-08-02"),
    ]

    assert fold_substantive_sections(manifests, from_version=1) == {"as_is", "to_be"}


def test_fold_ignores_versions_at_or_before_from_version():
    manifests = [
        ChangeManifest(version=2, changes=[SectionChange(section="as_is")],
                       recorded_on="2026-08-01"),
        ChangeManifest(version=3, changes=[SectionChange(section="to_be")],
                       recorded_on="2026-08-02"),
    ]

    assert fold_substantive_sections(manifests, from_version=2) == {"to_be"}


def test_text_only_edit_can_be_declared_editorial():
    old = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])
    new = _doc(as_is=[{"id": "as-1", "text": "紙の伝票を手入力", "visibility": "internal"}])

    assert is_text_only_change("as_is", old, new) is True


def test_added_node_cannot_be_declared_editorial():
    """宣言を無条件に信じると、追加・削除まで陳腐化判定から隠せてしまう。"""
    old = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])
    new = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"},
                      {"id": "as-2", "text": "追加", "visibility": "internal"}])

    assert is_text_only_change("as_is", old, new) is False


def test_confidence_change_cannot_be_declared_editorial():
    old = _doc(to_be=[{"id": "tb-1", "text": "自動化", "confidence": "assumed"}])
    new = _doc(to_be=[{"id": "tb-1", "text": "自動化", "confidence": "confirmed"}])

    assert is_text_only_change("to_be", old, new) is False


def test_fold_excludes_editorial_declarations():
    manifests = [
        ChangeManifest(
            version=2,
            changes=[SectionChange(section="as_is", change_kind="editorial")],
            recorded_on="2026-08-01",
        )
    ]

    assert fold_substantive_sections(manifests, from_version=1) == set()


def test_fold_excludes_id_only_migration_version():
    """初回ID採番は意味上の変更ではないため陳腐化を引き起こさない。"""
    manifests = [
        ChangeManifest(
            version=2,
            changes=[SectionChange(section="challenges")],
            id_only_migration=True,
            recorded_on="2026-08-01",
        )
    ]

    assert fold_substantive_sections(manifests, from_version=1) == set()


def test_store_round_trips_manifests_in_version_order(tmp_path):
    store = ManifestStore(LocalJsonStorage(tmp_path))
    store.save("p1", ChangeManifest(version=1, recorded_on="2026-08-01"))
    store.save("p1", ChangeManifest(version=2, changes=[SectionChange(section="to_be")],
                                    recorded_on="2026-08-02"))

    assert [m.version for m in store.list("p1")] == [1, 2]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_core.manifest'`

- [ ] **Step 3: 実装**

`core/src/medo_core/manifest.py`:

```python
"""要件の版ごとの変更記録。

陳腐化判定は「生成物の要件版から最新版まで」を比較するため、保存時にしか
分からない情報(editorial宣言・ID初回採番)を後から再現できる必要がある。
"""

from typing import Literal

from pydantic import BaseModel, Field

from medo_core.storage import Storage

TRACKED_SECTIONS = [
    "industry", "background", "goal", "principles", "functional", "non_functional",
    "sources", "as_is", "to_be", "kpis", "stakeholders", "gaps", "bottlenecks",
    "challenges", "constraints", "attempts", "hypotheses", "open_questions",
]


class SectionChange(BaseModel):
    section: str
    change_kind: Literal["substantive", "editorial"] = "substantive"


class ChangeManifest(BaseModel):
    version: int
    changes: list[SectionChange] = Field(default_factory=list)
    id_only_migration: bool = False
    recorded_on: str


EMPTY_SECTION = {"non_functional": {}, "industry": "", "background": "", "goal": ""}


def changed_sections(old: dict, new: dict) -> list[str]:
    """2つの要件ドキュメント(dict)で値が異なるセクション名を返す。

    意味差の推測はしない。値が異なるかどうかだけを見る。
    初版(old={})では、既定値のまま埋まっていないセクションを変更として数えない。
    """
    def value(doc: dict, section: str):
        return doc.get(section, EMPTY_SECTION.get(section, []))

    return [s for s in TRACKED_SECTIONS if value(old, s) != value(new, s)]


def is_text_only_change(section: str, old: dict, new: dict) -> bool:
    """そのセクションの差分が text の書き換えだけかを判定する。

    editorial 宣言を無条件に信じると、ノードの追加・削除や confidence 変更まで
    「誤字修正」として陳腐化判定から隠せてしまう。宣言できる範囲を機械的に絞る。
    """
    if section in SCALAR_TEXT_SECTIONS:
        return True
    old_nodes = old.get(section) or []
    new_nodes = new.get(section) or []
    if not isinstance(old_nodes, list) or not isinstance(new_nodes, list):
        return False
    if len(old_nodes) != len(new_nodes):
        return False
    if not all(isinstance(n, dict) for n in (*old_nodes, *new_nodes)):
        return False
    for before, after in zip(old_nodes, new_nodes, strict=True):
        if {k: v for k, v in before.items() if k != "text"} != \
                {k: v for k, v in after.items() if k != "text"}:
            return False
    return True


def fold_sections(
    manifests: list[ChangeManifest], from_version: int, change_kind: str
) -> set[str]:
    """from_version より後の全manifestを畳み込み、指定種別の変更セクションを返す。"""
    sections: set[str] = set()
    for m in manifests:
        if m.version <= from_version or m.id_only_migration:
            continue
        sections.update(c.section for c in m.changes if c.change_kind == change_kind)
    return sections


def fold_substantive_sections(
    manifests: list[ChangeManifest], from_version: int
) -> set[str]:
    return fold_sections(manifests, from_version, "substantive")


class ManifestStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _prefix(self, project_id: str) -> str:
        return f"projects/{project_id}/manifests"

    def save(self, project_id: str, manifest: ChangeManifest) -> None:
        self._storage.put(
            f"{self._prefix(project_id)}/v{manifest.version}",
            manifest.model_dump(mode="json"),
        )

    def list(self, project_id: str) -> list[ChangeManifest]:
        manifests = [
            ChangeManifest.model_validate(self._storage.get(p))
            for p in self._storage.list(self._prefix(project_id))
        ]
        return sorted(manifests, key=lambda m: m.version)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_manifest.py -v`
Expected: 9 passed

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/manifest.py core/tests/test_manifest.py
git commit -m "feat(core): 変更manifestとセクション差分を追加

change_kind をセクション別に持つ。文書全体で単一の値にすると
「AsIsは誤字修正、ToBeは実質変更」を表現できず、フィールド別の
陳腐化判定をmanifestから再現できない。"
```

---

## Task 5: RequirementsDoc の拡張と既存データの移行

**Files:**
- Modify: `core/src/medo_core/requirements.py`
- Modify: `core/tests/test_requirements.py`

**Interfaces:**
- Consumes: Task 1〜3 のノード型
- Produces: 拡張された `RequirementsDoc`(`as_is` / `to_be` / `kpis` / `stakeholders` / `gaps` / `bottlenecks` / `constraints` / `attempts` / `hypotheses` を追加、`challenges: list[Challenge]` / `open_questions: list[OpenQuestion]` へ型変更)

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_requirements.py` に追記:

```python
from medo_core.nodes import AsIs, Challenge, OpenQuestion
from medo_core.requirements import RequirementsDoc


def test_open_questions_accepts_legacy_string_list():
    """フェーズ1のデータは list[str]。読み込み時にID付きへ変換する。"""
    doc = RequirementsDoc.model_validate(
        {"project": "p1", "open_questions": ["予算は未確定"]}
    )

    assert doc.open_questions[0].text == "予算は未確定"
    assert doc.open_questions[0].id == ""


def test_open_questions_accepts_new_object_form():
    doc = RequirementsDoc.model_validate(
        {"project": "p1", "open_questions": [{"id": "oq-1", "text": "予算は未確定"}]}
    )

    assert doc.open_questions[0].id == "oq-1"


def test_challenges_reads_legacy_confidence_item_without_id():
    """Challenge は ConfidenceItem の上位互換。既存JSONはidが無い状態で読める。"""
    doc = RequirementsDoc.model_validate(
        {"project": "p1", "challenges": [{"text": "後戻りが起きる", "confidence": "confirmed"}]}
    )

    assert doc.challenges[0].id == ""
    assert doc.challenges[0].confidence == "confirmed"
    assert doc.challenges[0].scope == "core"


def test_new_sections_default_to_empty():
    doc = RequirementsDoc(project="p1")

    assert doc.as_is == []
    assert doc.to_be == []
    assert doc.attempts == []


def test_holds_as_is_nodes():
    doc = RequirementsDoc(
        project="p1",
        as_is=[AsIs(id="as-1", text="紙の伝票を手入力", visibility="internal")],
    )

    assert doc.as_is[0].visibility == "internal"


def test_diff_compares_open_questions_by_text():
    """pydanticモデルはhashableでないため、既存のset比較では落ちる。"""
    from medo_core.storage import LocalJsonStorage

    store = RequirementsStore(LocalJsonStorage(tmp_path_factory.mktemp("d")))
    store.save("p1", RequirementsDoc(project="p1",
        open_questions=[OpenQuestion(text="予算は未確定")]))
    doc = store.get("p1")
    doc.open_questions.append(OpenQuestion(text="体制は未確定"))
    store.save("p1", doc)

    assert store.diff("p1")["open_questions_added"] == ["体制は未確定"]


def test_challenge_and_open_question_are_node_types():
    doc = RequirementsDoc(
        project="p1",
        challenges=[Challenge(text="後戻り")],
        open_questions=[OpenQuestion(text="予算")],
    )

    assert isinstance(doc.challenges[0], Challenge)
    assert isinstance(doc.open_questions[0], OpenQuestion)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_requirements.py -v`
Expected: FAIL — `open_questions[0]` が文字列のまま(`AttributeError: 'str' object has no attribute 'text'`)

- [ ] **Step 3: `RequirementsDoc` を拡張**

`core/src/medo_core/requirements.py` を変更:

```python
from pydantic import BaseModel, Field, field_validator

from medo_core.nodes import (
    AsIs,
    Attempt,
    Bottleneck,
    Challenge,
    Confidence,
    Constraint,
    Gap,
    Hypothesis,
    Kpi,
    OpenQuestion,
    Stakeholder,
    ToBe,
)


class RequirementsDoc(BaseModel):
    project: str
    version: int = 1
    industry: str = ""
    background: str = ""
    goal: str = ""
    principles: list[ConfidenceItem] = Field(default_factory=list)
    functional: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional: dict[str, str] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    knowledge_backend: Literal["markdown", "sqlite"] = "markdown"

    challenges: list[Challenge] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)

    as_is: list[AsIs] = Field(default_factory=list)
    to_be: list[ToBe] = Field(default_factory=list)
    kpis: list[Kpi] = Field(default_factory=list)
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    bottlenecks: list[Bottleneck] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    attempts: list[Attempt] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)

    @field_validator("open_questions", mode="before")
    @classmethod
    def _accept_legacy_string_list(cls, value):
        if isinstance(value, list):
            return [{"text": v} if isinstance(v, str) else v for v in value]
        return value
```

`ConfidenceItem` と `FunctionalRequirement` は既存のまま残す(`principles` / `functional` が使う)。`Confidence` は `nodes.py` からの再エクスポートに切り替え、既存のimport経路(`from medo_core.requirements import Confidence`)を壊さない。

**`diff()` を同時に直す**。既存実装は `set(old.open_questions)` を使っており、`OpenQuestion` は pydantic モデルで hashable でないため `TypeError` になる。テキストで比較する:

```python
        old_q = {q.text for q in old.open_questions}
        new_q = {q.text for q in new.open_questions}
```

CLIの digest 出力(`? {q}`)も `q.text` に変える。

- [ ] **Step 4: 既存テストのfixtureを `Challenge` へ移行する**

**既存JSONは読めるが、`ConfidenceItem` の*インスタンス*は読めない**。pydanticは別モデルのインスタンスを自動変換しないため、`challenges=[ConfidenceItem(...)]` と書いているテストが `ValidationError` になる。本番の経路(JSON読み込み)は dict なので影響を受けない。

対象は2箇所:

```python
# core/tests/test_requirements.py / core/tests/test_status.py
challenges=[Challenge(text="外国語の電話予約に対応できず機会損失")]
```

`principles` / `functional` は `ConfidenceItem` のままでよい(型を変えていない)。

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run pytest core/tests/ -v`
Expected: 全て pass(既存の `test_requirements.py` / `test_status.py` も含む)

- [ ] **Step 6: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/requirements.py core/tests/test_requirements.py \
        core/tests/test_status.py cli/src/medo_cli/main.py
git commit -m "feat(core): 要件ドキュメントに論理連鎖のセクションを追加

open_questions を list[str] からID付きへ変更する。レビュー所見が
未確定事項を参照する必要があるが、文字列のリストでは参照先を指せない。
既存データは before-validator で読めるようにする。"
```

---

## Task 6: 保存時の採番と参照整合性検証

**Files:**
- Modify: `core/src/medo_core/requirements.py`
- Modify: `core/tests/test_requirements.py`

**Interfaces:**
- Consumes: Task 1 の `IdWatermarkStore`、Task 2〜3 のノード型、Task 4 の `ManifestStore` / `changed_sections`
- Produces: `RequirementsStore.save(project_id, doc, *, editorial_sections=(), today=None) -> int`(採番・検証・manifest保存を含む)、`RequirementsStore.__init__(storage)` は変更なし

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_requirements.py` に追記:

```python
from datetime import date

import pytest

from medo_core.nodes import AsIs, Challenge, Gap, ToBe
from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.storage import LocalJsonStorage

TODAY = date(2026, 8, 30)


def _store(tmp_path) -> RequirementsStore:
    return RequirementsStore(LocalJsonStorage(tmp_path))


def test_save_assigns_ids_to_empty_id_nodes(tmp_path):
    store = _store(tmp_path)
    doc = RequirementsDoc(
        project="p1",
        as_is=[AsIs(text="手作業", visibility="internal"), AsIs(text="公表", visibility="public")],
    )

    store.save("p1", doc, today=TODAY)

    saved = store.get("p1")
    assert [n.id for n in saved.as_is] == ["as-1", "as-2"]


def test_save_does_not_reuse_id_of_deleted_node(tmp_path):
    store = _store(tmp_path)
    store.save("p1", RequirementsDoc(project="p1",
        as_is=[AsIs(text="a", visibility="internal"), AsIs(text="b", visibility="internal")]),
        today=TODAY)
    kept = store.get("p1").as_is[0]

    store.save("p1", RequirementsDoc(project="p1", as_is=[kept]), today=TODAY)
    store.save("p1", RequirementsDoc(project="p1",
        as_is=[kept, AsIs(text="c", visibility="internal")]), today=TODAY)

    assert [n.id for n in store.get("p1").as_is] == ["as-1", "as-3"]


def test_save_rejects_duplicate_ids_within_document(tmp_path):
    store = _store(tmp_path)
    doc = RequirementsDoc(project="p1", as_is=[
        AsIs(id="as-1", text="a", visibility="internal"),
        AsIs(id="as-1", text="b", visibility="internal"),
    ])

    with pytest.raises(ValueError, match="重複"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_id_absent_from_previous_version(tmp_path):
    """ホストLLMが書き写す際の勝手なリナンバリングを機械的に検出する。"""
    store = _store(tmp_path)
    store.save("p1", RequirementsDoc(project="p1",
        as_is=[AsIs(text="a", visibility="internal")]), today=TODAY)

    doc = RequirementsDoc(project="p1", as_is=[AsIs(id="as-9", text="a", visibility="internal")])

    with pytest.raises(ValueError, match="as-9"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_link_to_unknown_node(tmp_path):
    store = _store(tmp_path)
    doc = RequirementsDoc(project="p1",
        gaps=[Gap(text="乖離", kind="goal", from_as_is=["as-99"])])

    with pytest.raises(ValueError, match="as-99"):
        store.save("p1", doc, today=TODAY)


def test_save_records_manifest_of_changed_sections(tmp_path):
    from medo_core.manifest import ManifestStore

    storage = LocalJsonStorage(tmp_path)
    store = RequirementsStore(storage)
    store.save("p1", RequirementsDoc(project="p1"), today=TODAY)
    store.save("p1", RequirementsDoc(project="p1",
        to_be=[ToBe(text="自動化されている")]), today=TODAY)

    manifests = ManifestStore(storage).list("p1")
    assert [c.section for c in manifests[1].changes] == ["to_be"]


def test_save_marks_declared_sections_as_editorial(tmp_path):
    from medo_core.manifest import ManifestStore

    storage = LocalJsonStorage(tmp_path)
    store = RequirementsStore(storage)
    store.save("p1", RequirementsDoc(project="p1", to_be=[ToBe(id="", text="自動化")]),
               today=TODAY)
    kept = store.get("p1").to_be[0]
    store.save("p1", RequirementsDoc(project="p1",
        to_be=[kept.model_copy(update={"text": "自動化されている"})]),
        editorial_sections=("to_be",), today=TODAY)

    manifests = ManifestStore(storage).list("p1")
    assert manifests[1].changes[0].change_kind == "editorial"


def test_save_flags_first_id_assignment_as_id_only_migration(tmp_path):
    """初回ID採番だけの保存は陳腐化を引き起こさない。"""
    from medo_core.manifest import ManifestStore

    storage = LocalJsonStorage(tmp_path)
    storage.put("projects/p1/requirements/v1", {
        "project": "p1", "version": 1,
        "challenges": [{"text": "後戻りが起きる", "confidence": "confirmed"}],
    })
    store = RequirementsStore(storage)
    doc = store.get("p1")

    store.save("p1", doc, today=TODAY)

    manifests = ManifestStore(storage).list("p1")
    assert manifests[-1].id_only_migration is True


def test_save_rejects_bottleneck_that_is_not_confirmed(tmp_path):
    """bottlenecks は検証・合意済みの真因のみを持つ。"""
    from medo_core.nodes import Bottleneck

    store = _store(tmp_path)
    doc = RequirementsDoc(project="p1", bottlenecks=[Bottleneck(text="承認3階層")])

    with pytest.raises(ValueError, match="confirmed"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_perception_gap_without_both_visibilities(tmp_path):
    store = _store(tmp_path)
    store.save("p1", RequirementsDoc(project="p1",
        as_is=[AsIs(text="公表", visibility="public")]), today=TODAY)
    public_id = store.get("p1").as_is[0].id

    doc = RequirementsDoc(project="p1",
        as_is=[store.get("p1").as_is[0]],
        gaps=[Gap(text="乖離", kind="perception", from_as_is=[public_id])])

    with pytest.raises(ValueError, match="perception"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_bottleneck_promoted_from_unvalidated_hypothesis(tmp_path):
    from medo_core.nodes import Bottleneck, Hypothesis

    store = _store(tmp_path)
    store.save("p1", RequirementsDoc(project="p1",
        hypotheses=[Hypothesis(kind="cause", statement="承認階層が原因")]), today=TODAY)
    hyp = store.get("p1").hypotheses[0]

    doc = RequirementsDoc(project="p1", hypotheses=[hyp],
        bottlenecks=[Bottleneck(text="承認3階層", confidence="confirmed",
                                from_hypothesis=hyp.id)])

    with pytest.raises(ValueError, match="validated"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_evidenced_by_pointing_to_unknown_node(tmp_path):
    store = _store(tmp_path)
    doc = RequirementsDoc(project="p1",
        to_be=[ToBe(text="自動化", evidenced_by=["as-99"])])

    with pytest.raises(ValueError, match="as-99"):
        store.save("p1", doc, today=TODAY)


def test_save_accepts_evidenced_by_pointing_to_event(tmp_path):
    """誰の発言が理想像を形にしたかをイベントまで遡れるようにする。"""
    store = _store(tmp_path)

    store.save("p1", RequirementsDoc(project="p1",
        to_be=[ToBe(text="自動化", evidenced_by=["ev-3"])]), today=TODAY)

    assert store.get("p1").to_be[0].evidenced_by == ["ev-3"]


def test_save_rejects_promotion_source_pointing_to_goal_gap(tmp_path):
    from medo_core.nodes import PromotionSource

    store = _store(tmp_path)
    store.save("p1", RequirementsDoc(project="p1", gaps=[Gap(text="乖離", kind="goal")]),
               today=TODAY)
    gap_id = store.get("p1").gaps[0].id

    doc = RequirementsDoc(project="p1",
        gaps=[store.get("p1").gaps[0]],
        challenges=[Challenge(text="どちらを前提にするか",
            promoted_from=PromotionSource(kind="internal_conflict", ref=gap_id))])

    with pytest.raises(ValueError, match="internal_conflict"):
        store.save("p1", doc, today=TODAY)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_requirements.py -v`
Expected: FAIL — `TypeError: save() got an unexpected keyword argument 'today'`

- [ ] **Step 3: 採番と検証を実装**

`core/src/medo_core/requirements.py` の `RequirementsStore` を変更:

```python
from datetime import date

from medo_core.manifest import ChangeManifest, ManifestStore, SectionChange, changed_sections
from medo_core.nodes import ID_PREFIXES
from medo_core.watermark import IdWatermarkStore

# 参照フィールド → 参照先セクション。保存時に参照先の実在を検証する。
LINK_FIELDS = {
    "gaps": {"from_as_is": "as_is", "from_to_be": "to_be"},
    "bottlenecks": {"gap_ids": "gaps"},
    "challenges": {"bottleneck_ids": "bottlenecks", "cause_hypothesis_ids": "hypotheses"},
    "kpis": {"to_be_ids": "to_be"},
    "attempts": {"challenge_ids": "challenges", "gap_ids": "gaps"},
    "hypotheses": {"challenge_ids": "challenges"},
    "as_is": {"source_stakeholder_ids": "stakeholders"},
}


class RequirementsStore:
    def __init__(self, storage: Storage):
        self._storage = storage
        self._watermarks = IdWatermarkStore(storage)
        self._manifests = ManifestStore(storage)

    def save(
        self,
        project_id: str,
        doc: RequirementsDoc,
        *,
        editorial_sections: tuple[str, ...] = (),
        today: date | None = None,
    ) -> int:
        previous = self.get(project_id)
        self._reject_duplicate_ids(doc)
        self._reject_unknown_existing_ids(doc, previous)
        doc = self._assign_ids(project_id, doc)
        self._validate_links(doc)
        self._validate_domain_rules(doc)

        version = self.latest_version(project_id) + 1
        doc = doc.model_copy(update={"version": version, "project": project_id})
        self._storage.put(self._path(project_id, version), doc.model_dump(mode="json"))
        self._record_manifest(project_id, previous, doc, editorial_sections, today)
        return version
```

補助メソッドを同クラスに実装する:

```python
    def _iter_sections(self, doc: RequirementsDoc):
        for section in ID_PREFIXES:
            yield section, getattr(doc, section)

    def _reject_duplicate_ids(self, doc: RequirementsDoc) -> None:
        seen: set[str] = set()
        for _, nodes in self._iter_sections(doc):
            for n in nodes:
                if not n.id:
                    continue
                if n.id in seen:
                    raise ValueError(f"IDが重複しています: {n.id}")
                seen.add(n.id)

    def _reject_unknown_existing_ids(
        self, doc: RequirementsDoc, previous: RequirementsDoc | None
    ) -> None:
        known = set()
        if previous:
            for _, nodes in self._iter_sections(previous):
                known.update(n.id for n in nodes if n.id)
        for _, nodes in self._iter_sections(doc):
            for n in nodes:
                if n.id and n.id not in known:
                    raise ValueError(
                        f"直前バージョンに存在しないIDです: {n.id}"
                        "(リナンバリングは許可されません)"
                    )

    def _assign_ids(self, project_id: str, doc: RequirementsDoc) -> RequirementsDoc:
        watermark = self._watermarks.load(project_id)
        updates = {}
        for section, nodes in self._iter_sections(doc):
            blanks = [i for i, n in enumerate(nodes) if not n.id]
            if not blanks:
                continue
            new_ids = watermark.allocate(ID_PREFIXES[section], len(blanks))
            assigned = list(nodes)
            for i, new_id in zip(blanks, new_ids, strict=True):
                assigned[i] = assigned[i].model_copy(update={"id": new_id})
            updates[section] = assigned
        self._watermarks.save(project_id, watermark)
        return doc.model_copy(update=updates) if updates else doc

    def _validate_links(self, doc: RequirementsDoc) -> None:
        ids_by_section = {
            section: {n.id for n in nodes} for section, nodes in self._iter_sections(doc)
        }
        for section, fields in LINK_FIELDS.items():
            for node in getattr(doc, section):
                for field, target in fields.items():
                    for ref in getattr(node, field):
                        if ref not in ids_by_section[target]:
                            raise ValueError(
                                f"{section}.{field} の参照先が存在しません: {ref}"
                            )
```

`_validate_domain_rules` はドメイン固有の不変条件をまとめる:

```python
    def _validate_domain_rules(self, doc: RequirementsDoc) -> None:
        as_is_by_id = {n.id: n for n in doc.as_is}

        for gap in doc.gaps:
            refs = [as_is_by_id[i] for i in gap.from_as_is]
            if gap.kind == "perception":
                kinds = {n.visibility for n in refs}
                if kinds != {"public", "internal"}:
                    raise ValueError(
                        "perception gap は public と internal の AsIs を"
                        "それぞれ1件以上参照する必要があります"
                    )
            if gap.kind == "internal_conflict":
                internals = [n for n in refs if n.visibility == "internal"]
                stakeholder_sets = {frozenset(n.source_stakeholder_ids) for n in internals}
                if len(internals) < 2 or len(stakeholder_sets) < 2:
                    raise ValueError(
                        "internal_conflict gap は視点の異なる internal な AsIs を"
                        "2件以上参照する必要があります"
                    )
            if gap.kind != "goal" and gap.from_to_be:
                raise ValueError(f"{gap.kind} gap は from_to_be を持てません")

        goal_gap_ids = {g.id for g in doc.gaps if g.kind == "goal"}
        for bn in doc.bottlenecks:
            if bn.confidence != "confirmed":
                raise ValueError(
                    f"bottleneck {bn.id} は confirmed のみ保存できます"
                    "(未検証の真因は hypotheses(kind='cause')に置く)"
                )
            for gid in bn.gap_ids:
                if gid not in goal_gap_ids:
                    raise ValueError(f"bottleneck が参照できるのは goal gap のみです: {gid}")

        conflict_gap_ids = {g.id for g in doc.gaps if g.kind == "internal_conflict"}
        for ch in doc.challenges:
            src = ch.promoted_from
            if src and src.kind == "internal_conflict" and src.ref not in conflict_gap_ids:
                raise ValueError(
                    f"promoted_from(internal_conflict)の参照先が"
                    f"internal_conflict gap ではありません: {src.ref}"
                )

        validated_causes = {
            h.id for h in doc.hypotheses
            if h.kind == "cause" and h.status == "validated"
        }
        for bn in doc.bottlenecks:
            if bn.from_hypothesis and bn.from_hypothesis not in validated_causes:
                raise ValueError(
                    "from_hypothesis は kind='cause' かつ status='validated' の仮説のみ"
                    f"参照できます: {bn.from_hypothesis}"
                )

        node_ids = {n.id for _, nodes in self._iter_sections(doc) for n in nodes}
        for tb in doc.to_be:
            for ref in tb.evidenced_by:
                if not ref.startswith("ev-") and ref not in node_ids:
                    raise ValueError(f"evidenced_by の参照先が存在しません: {ref}")
```

**イベントID(`ev-N`)を参照する検証はここでは行わない**。`RequirementsStore` は EventStore を持たないため、`ev-` 始まりは通過させる。実体は **Task 13 の `WorkflowRecorder._validate_cross_store_refs`** が持つ(対象: `ToBe.evidenced_by` / `PromotionSource(kind="undeterminable")` / `Hypothesis.fermi_ref`)。

**この分割により、`RequirementsStore.save` を直接呼ぶと他ストア参照が未検証のまま通る**。CLIとSkillの経路は必ず `WorkflowRecorder.save_requirements` を通す(Task 16 Step 4)。

manifest記録:

```python
    def _record_manifest(
        self,
        project_id: str,
        previous: RequirementsDoc | None,
        saved: RequirementsDoc,
        editorial_sections: tuple[str, ...],
        today: date | None,
    ) -> None:
        old = previous.model_dump(mode="json") if previous else {}
        new = saved.model_dump(mode="json")
        sections = changed_sections(old, new)
        editorial_sections = tuple(
            s for s in editorial_sections if is_text_only_change(s, old, new)
        )
        id_only = previous is not None and self._is_id_only_change(previous, saved)
        self._manifests.save(project_id, ChangeManifest(
            version=saved.version,
            changes=[
                SectionChange(
                    section=s,
                    change_kind="editorial" if s in editorial_sections else "substantive",
                )
                for s in sections
            ],
            id_only_migration=id_only,
            recorded_on=(today or date.today()).isoformat(),
        ))

    def _is_id_only_change(self, previous: RequirementsDoc, saved: RequirementsDoc) -> bool:
        """ID以外のフィールドが同一なら初回採番のみの保存とみなす。"""
        def strip_ids(doc: RequirementsDoc) -> dict:
            data = doc.model_dump(mode="json")
            for section in ID_PREFIXES:
                for node in data.get(section, []):
                    node.pop("id", None)
            data.pop("version", None)
            return data

        return strip_ids(previous) == strip_ids(saved)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/ -v`
Expected: 全て pass

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/requirements.py core/tests/test_requirements.py
git commit -m "feat(core): 保存時の採番と参照整合性検証を追加

ホストLLMが要件を書き写す際の勝手なリナンバリングを機械的に検出する。
直前バージョンに存在しないIDを拒否することで、別のノードを指す
リンクへの静かなすり替わりを防ぐ。"
```

---

## Task 7: 要件CLIの拡張

**Files:**
- Modify: `cli/src/medo_cli/main.py`
- Modify: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 6 の `RequirementsStore.save(..., editorial_sections=...)`
- Produces: `medo requirements save --file <path> [--editorial <section>]...`(既存の save に `--editorial` を追加)、失敗時は exit code 1 + stderr に `error: <理由>`

- [ ] **Step 1: 失敗するテストを書く**

`cli/tests/test_cli.py` に追記:

```python
import json


def test_requirements_save_accepts_new_sections(tmp_path, runner):
    doc = {
        "project": "p1",
        "as_is": [{"text": "紙の伝票を手入力", "visibility": "internal"}],
    }
    f = tmp_path / "req.json"
    f.write_text(json.dumps(doc), encoding="utf-8")

    result = runner.invoke(app, ["requirements", "save", "--project", "p1", "--file", str(f)])

    assert result.exit_code == 0
    assert "saved: v1" in result.stdout


def test_requirements_save_reports_validation_error_without_guessing(tmp_path, runner):
    doc = {"project": "p1", "gaps": [{"text": "乖離", "from_as_is": ["as-99"]}]}
    f = tmp_path / "req.json"
    f.write_text(json.dumps(doc), encoding="utf-8")

    result = runner.invoke(app, ["requirements", "save", "--project", "p1", "--file", str(f)])

    assert result.exit_code == 1
    assert "as-99" in result.stderr


def test_requirements_save_declares_editorial_sections(tmp_path, runner):
    doc = {"project": "p1", "to_be": [{"text": "自動化"}]}
    f = tmp_path / "req.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    runner.invoke(app, ["requirements", "save", "--project", "p1", "--file", str(f)])

    saved = json.loads(f.read_text(encoding="utf-8"))
    saved["to_be"] = [{"id": "tb-1", "text": "自動化されている"}]
    f.write_text(json.dumps(saved), encoding="utf-8")
    result = runner.invoke(app, [
        "requirements", "save", "--project", "p1", "--file", str(f), "--editorial", "to_be",
    ])

    assert result.exit_code == 0
    assert "saved: v2" in result.stdout
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest cli/tests/test_cli.py -k editorial -v`
Expected: FAIL — `no such option: --editorial`

- [ ] **Step 3: CLIに `--editorial` を追加**

`cli/src/medo_cli/main.py` の `requirements save` コマンドに追加:

```python
@requirements_app.command("save")
def requirements_save(
    project: str = typer.Option(..., "--project"),
    file: Path = typer.Option(..., "--file"),
    editorial: list[str] = typer.Option(
        [], "--editorial",
        help="誤字・言い回しの修正のみと宣言するセクション名"
             "(text以外に差分があるセクションの宣言は無視される)",
    ),
) -> None:
    """要件ドキュメントを保存する(バージョンは自動採番)。"""
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
        doc = RequirementsDoc.model_validate(data)
        version = _requirements_store().save(
            project, doc, editorial_sections=tuple(editorial)
        )
    except Exception as e:
        _fail(f"要件の保存に失敗: {e}")
    typer.echo(f"saved: v{version}")
```

**既存の `yaml.safe_load` を維持する**(YAMLはJSONの上位集合なので両方読める。`json.loads` に置き換えるとYAML入力が壊れる)。**保存時の検証例外も `_fail()` の対象に含める** — Task 6 で `save` が `ValueError` を投げるようになったため、囲まないとスタックトレースがそのまま出る。

**この時点では `RequirementsStore.save` を直接呼ぶ**。`WorkflowRecorder` は Task 12 で作るため、節目検出への切り替えは **Task 16 Step 4** で行う(それまで `medo requirements save` は節目を記録しない)。

**例外は既存の `_fail()` パターンで扱う**。`main.py` には共通ハンドラが無く、各コマンドが `try/except` で `_fail(...)` を呼んでstderrへ `error: ` を出して exit 1 する。追加・変更するコマンドすべてで同じ形にする。

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest cli/tests/ -v`
Expected: 全て pass

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(cli): 要件保存にeditorial宣言を追加

誤字修正まで下流の全生成物をstale化すると再生成ループに陥る。
coreは意味差を推測しないため、保存者の明示的な宣言を入口に置く。"
```

---

## Task 8: 生成物の型拡張と依存グラフ

**Files:**
- Modify: `core/src/medo_core/artifacts.py`
- Modify: `core/tests/test_artifacts.py`

**Interfaces:**
- Consumes: なし(既存の `Artifact` を拡張)
- Produces: `ArtifactType` に `research` / `as-is-report` を追加、`Artifact.derived_from: list[str]` / `.slide_kind` / `.covered_challenge_ids`、`generated_by` に `codex` を追加、`ALLOWED_PARENTS: dict[tuple, tuple]`

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_artifacts.py` に追記:

```python
import pytest
from pydantic import ValidationError

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.storage import LocalJsonStorage


def _artifact(**kw) -> Artifact:
    base = {
        "project": "p1",
        "type": "as-is-report",
        "requirements_version": 1,
        "generated_by": "claude",
        "content": "# 現状",
    }
    base.update(kw)
    return Artifact.model_validate(base)


def test_slides_require_slide_kind():
    """親typeからの推論に頼ると、複数の親を持てる設計では判別が曖昧になる。"""
    with pytest.raises(ValidationError):
        _artifact(type="slides", content="---\nmarp: true")


def test_slides_accept_discussion_kind():
    a = _artifact(type="slides", slide_kind="discussion", derived_from=["as-is-report-v1"])

    assert a.slide_kind == "discussion"


def test_non_slides_reject_slide_kind():
    with pytest.raises(ValidationError):
        _artifact(type="research", slide_kind="discussion")


def test_rejected_option_records_why_it_was_dropped():
    """却下案の見送り理由が失われると、意思決定者の納得感が大きく変わる。"""
    from medo_core.artifacts import RejectedOption

    a = _artifact(type="comparison",
                  rejected_options=[RejectedOption(name="B案", reason="運用負荷が高い",
                                                   accepted_risk="初期費用が上がる")])

    assert a.rejected_options[0].accepted_risk == "初期費用が上がる"


def test_rejected_options_are_not_allowed_on_reporting_types():
    with pytest.raises(ValidationError):
        _artifact(type="as-is-report",
                  rejected_options=[{"name": "B案", "reason": "運用負荷"}])


def test_generated_by_accepts_codex():
    """どのホストからでも生成できる設計であり、来歴が追える必要がある。"""
    assert _artifact(generated_by="codex").generated_by == "codex"


def test_save_rejects_parent_of_disallowed_type(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(type="research", generated_by="claude", content="調査"))

    with pytest.raises(ValueError, match="derived_from"):
        store.save("p1", _artifact(type="slides", slide_kind="discussion",
                                   derived_from=["research-v1"]))


def test_save_rejects_missing_parent(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))

    with pytest.raises(ValueError, match="as-is-report-v9"):
        store.save("p1", _artifact(type="slides", slide_kind="discussion",
                                   derived_from=["as-is-report-v9"]))


def test_save_rejects_discussion_slides_without_exactly_one_parent(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))

    with pytest.raises(ValueError, match="ちょうど1"):
        store.save("p1", _artifact(type="slides", slide_kind="discussion"))


def test_save_rejects_as_is_report_with_multiple_research_parents(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(type="research", content="調査1"))
    store.save("p1", _artifact(type="research", content="調査2"))

    with pytest.raises(ValueError, match="0または1件"):
        store.save("p1", _artifact(derived_from=["research-v1", "research-v2"]))


def test_save_rejects_grown_from_option_absent_from_candidate_set(tmp_path):
    from medo_core.artifacts import GrownFrom, OptionMeta

    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(type="mini-prfaq", options=[OptionMeta(name="A案")],
                               content="候補"))

    with pytest.raises(ValueError, match="B案"):
        store.save("p1", _artifact(type="prfaq",
                                   grown_from=GrownFrom(artifact="mini-prfaq-v1",
                                                        option="B案"),
                                   content="育成"))


def test_save_rejects_older_requirements_version_than_latest_of_same_type(tmp_path):
    """祖先判定は requirements_version の単調性で行うため、逆行を拒否する。"""
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(requirements_version=3))

    with pytest.raises(ValueError, match="requirements_version"):
        store.save("p1", _artifact(requirements_version=2))


def test_save_rejects_cyclic_dependency(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(type="research", content="調査"))
    store.save("p1", _artifact(type="as-is-report", derived_from=["research-v1"]))
    storage = store._storage
    raw = storage.get("projects/p1/artifacts/research-v1")
    raw["derived_from"] = ["as-is-report-v1"]
    storage.put("projects/p1/artifacts/research-v1", raw)

    with pytest.raises(ValueError, match="循環"):
        store.save("p1", _artifact(type="slides", slide_kind="discussion",
                                   derived_from=["as-is-report-v1"]))
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_artifacts.py -v`
Expected: FAIL — `slide_kind` は未定義フィールドとして無視されるため、`test_slides_require_slide_kind` が `ValidationError` を上げず `Failed: DID NOT RAISE`、`test_slides_accept_discussion_kind` が `AttributeError: 'Artifact' object has no attribute 'slide_kind'`

- [ ] **Step 3: `Artifact` を拡張**

`core/src/medo_core/artifacts.py`:

```python
ArtifactType = Literal[
    "research", "as-is-report",
    "architecture", "slides", "mock", "comparison", "mini-prfaq", "prfaq", "fermi",
]

SlideKind = Literal["discussion", "final"]

# (子type, slide_kind) → (許容する親type, 必須か)
ALLOWED_PARENTS: dict[tuple[str, str | None], tuple[tuple[str, ...], bool]] = {
    ("as-is-report", None): (("research",), False),
    ("slides", "discussion"): (("as-is-report",), True),
    ("slides", "final"): (("prfaq",), True),
}

# カバレッジ判定を適用する型。現状の記述と共有が目的の型には適用しない。
COVERAGE_TYPES = ("mini-prfaq", "prfaq", "comparison", "architecture", "mock")

# 見送り理由を保持する型。判断は打ち手比較の段階で起きる。
REJECTION_TYPES = ("mini-prfaq", "comparison", "prfaq")


class RejectedOption(BaseModel):
    name: str
    reason: str                # なぜ見送ったか
    accepted_risk: str = ""    # 見送りによって受け入れたリスク


class Artifact(BaseModel):
    project: str
    type: ArtifactType
    version: int = 1
    requirements_version: int
    cited_knowledge: list[str] = Field(default_factory=list)
    cited_facts: list[str] = Field(default_factory=list)
    options: list[OptionMeta] = Field(default_factory=list)
    grown_from: GrownFrom | None = None
    derived_from: list[str] = Field(default_factory=list)
    slide_kind: SlideKind | None = None
    covered_challenge_ids: list[str] | None = None
    rejected_options: list[RejectedOption] = Field(default_factory=list)
    generated_by: Literal["claude", "codex", "gemini"] | None = None
    content: str

    @model_validator(mode="after")
    def _validate_type_rules(self) -> "Artifact":
        if self.type == "prfaq" and self.grown_from is None:
            raise ValueError(
                "prfaq には grown_from(育成元のミニPRFAQ候補セットと打ち手)が必須です"
            )
        if self.type == "slides" and self.slide_kind is None:
            raise ValueError("slides には slide_kind(discussion|final)が必須です")
        if self.rejected_options and self.type not in REJECTION_TYPES:
            raise ValueError(
                f"rejected_options を持てるのは {'/'.join(REJECTION_TYPES)} のみです"
            )
        if self.type != "slides" and self.slide_kind is not None:
            raise ValueError("slide_kind は slides でのみ指定できます")
        if self.type == "fermi":
            if self.generated_by is not None:
                raise ValueError("fermi はコードが生成するため generated_by は指定できません")
        elif self.generated_by is None:
            raise ValueError(f"{self.type} には generated_by(claude|codex|gemini)が必須です")
        return self
```

- [ ] **Step 4: `ArtifactStore.save` に依存検証を追加**

```python
    def save(self, project_id: str, artifact: Artifact) -> str:
        existing = {a_id: a for a_id, a in self._load_all(project_id).items()}
        self._validate_parents(artifact, existing)
        self._validate_grown_from(artifact, existing)
        self._validate_version_monotonicity(artifact, existing)

        versions = [
            int(a_id.rsplit("-v", 1)[1])
            for a_id in existing
            if a_id.startswith(f"{artifact.type}-v")
        ]
        version = max(versions, default=0) + 1
        artifact = artifact.model_copy(update={"version": version, "project": project_id})
        artifact_id = f"{artifact.type}-v{version}"
        self._detect_cycle(artifact_id, artifact, existing)
        self._storage.put(
            f"{self._prefix(project_id)}/{artifact_id}", artifact.model_dump(mode="json")
        )
        return artifact_id

    def _load_all(self, project_id: str) -> dict[str, Artifact]:
        return {
            p.rsplit("/", 1)[1]: Artifact.model_validate(self._storage.get(p))
            for p in self._storage.list(self._prefix(project_id))
        }

    def _validate_parents(self, artifact: Artifact, existing: dict[str, Artifact]) -> None:
        rule = ALLOWED_PARENTS.get((artifact.type, artifact.slide_kind))
        if rule is None:
            if artifact.derived_from:
                raise ValueError(f"{artifact.type} は derived_from を持てません")
            return
        allowed_types, required = rule
        if required and len(artifact.derived_from) != 1:
            raise ValueError(
                f"{artifact.type}({artifact.slide_kind})の親はちょうど1件必要です"
            )
        if not required and len(artifact.derived_from) > 1:
            raise ValueError(f"{artifact.type} の親は0または1件です")
        for parent_id in artifact.derived_from:
            parent = existing.get(parent_id)
            if parent is None:
                raise ValueError(f"derived_from の親が存在しません: {parent_id}")
            if parent.type not in allowed_types:
                raise ValueError(
                    f"derived_from に許容されない親typeです: {parent_id}({parent.type})"
                )

    def _validate_grown_from(self, artifact: Artifact, existing: dict[str, Artifact]) -> None:
        if artifact.grown_from is None:
            return
        parent = existing.get(artifact.grown_from.artifact)
        if parent is None:
            raise ValueError(f"grown_from の候補セットが存在しません: "
                             f"{artifact.grown_from.artifact}")
        if artifact.grown_from.option not in {o.name for o in parent.options}:
            raise ValueError(
                f"grown_from の打ち手が候補セットに存在しません: {artifact.grown_from.option}"
            )

    def _validate_version_monotonicity(
        self, artifact: Artifact, existing: dict[str, Artifact]
    ) -> None:
        same_type = [a for a in existing.values() if a.type == artifact.type]
        if not same_type:
            return
        newest = max(a.requirements_version for a in same_type)
        if artifact.requirements_version < newest:
            raise ValueError(
                f"同じtypeの既存最新版より古い requirements_version では保存できません"
                f"(既存: {newest} / 指定: {artifact.requirements_version})"
            )

    def _detect_cycle(
        self, artifact_id: str, artifact: Artifact, existing: dict[str, Artifact]
    ) -> None:
        graph = {a_id: a.derived_from for a_id, a in existing.items()}
        graph[artifact_id] = artifact.derived_from
        visiting: set[str] = set()

        def walk(node: str) -> None:
            if node in visiting:
                raise ValueError(f"derived_from が循環しています: {node}")
            visiting.add(node)
            for parent in graph.get(node, []):
                walk(parent)
            visiting.discard(node)

        walk(artifact_id)
```

- [ ] **Step 5: 既存テストのfixtureを有効な状態に直す**

新しい `grown_from` 検証は、**既存fixtureが作っていた不正な状態を正しく拒否する**。`core/tests/test_status.py` の `_mini()` は `options` が空のまま、`_prfaq()` が存在しない打ち手を `grown_from.option` に指している。

```python
def _mini(**kw) -> Artifact:
    base = dict(
        project="yoyaku", type="mini-prfaq", requirements_version=1,
        generated_by="claude", content="# 候補セット",
        options=[OptionMeta(name="多言語AI音声予約")],
    )
```

`core/tests/test_artifacts.py` の既存ヘルパー `_artifact` は、Task 8 で追加するヘルパーと同名になる。**既存側を改名して両方を残す**(既存テストの意図を壊さない)。

- [ ] **Step 6: テストが通ることを確認**

Run: `uv run pytest -v`
Expected: 全て pass(既存の `test_status.py` も含む)

- [ ] **Step 7: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/artifacts.py core/tests/test_artifacts.py core/tests/test_status.py
git commit -m "feat(core): 生成物に複数依存と用途フィールドを追加

単一の任意親では、依存を書き忘れたときに陳腐化が伝播しない穴が残る。
slidesの用途は親typeから推論せず一級フィールドで持つ。"
```

---

## Task 9: セクション依存によるstale判定とstale伝播

**Files:**
- Modify: `core/src/medo_core/artifacts.py`
- Modify: `core/tests/test_artifacts.py`

**Interfaces:**
- Consumes: Task 4 の `fold_substantive_sections` / `ManifestStore`、Task 8 の `Artifact`
- Produces: `DEPENDENT_SECTIONS: dict[tuple[str, str | None], tuple[str, ...]]`、`ArtifactStore.freshness(project_id, latest_requirements_version, core_challenge_ids) -> dict[str, Freshness]`、`Freshness(state, reasons)`

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_artifacts.py` に追記:

```python
from medo_core.manifest import ChangeManifest, ManifestStore, SectionChange


def _manifest(version: int, *sections: str, editorial: bool = False) -> ChangeManifest:
    return ChangeManifest(
        version=version,
        changes=[
            SectionChange(
                section=s, change_kind="editorial" if editorial else "substantive"
            )
            for s in sections
        ],
        recorded_on="2026-08-30",
    )


def test_research_is_not_stale_when_requirements_change(tmp_path):
    """調査結果は要件が変わっても陳腐化しない。引用ファクトの鮮度でのみ古くなる。"""
    storage = LocalJsonStorage(tmp_path)
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="research", requirements_version=1, content="調査"))
    ManifestStore(storage).save("p1", _manifest(2, "as_is", "to_be"))

    freshness = store.freshness("p1", latest_requirements_version=2, core_challenge_ids=set())

    assert freshness["research-v1"].state == "current"


def test_as_is_report_is_stale_when_dependent_section_changed(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="as-is-report", requirements_version=1))
    ManifestStore(storage).save("p1", _manifest(2, "as_is"))

    freshness = store.freshness("p1", latest_requirements_version=2, core_challenge_ids=set())

    assert freshness["as-is-report-v1"].state == "stale"
    assert "as_is" in freshness["as-is-report-v1"].reasons[0]


def test_as_is_report_is_current_when_unrelated_section_changed(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="as-is-report", requirements_version=1))
    ManifestStore(storage).save("p1", _manifest(2, "functional"))

    freshness = store.freshness("p1", latest_requirements_version=2, core_challenge_ids=set())

    assert freshness["as-is-report-v1"].state == "current"


def test_editorial_change_marks_artifact_outdated_not_stale(tmp_path):
    """再生成は要らないが、差分の確認は促す。"""
    storage = LocalJsonStorage(tmp_path)
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="as-is-report", requirements_version=1))
    ManifestStore(storage).save("p1", _manifest(2, "as_is", editorial=True))

    freshness = store.freshness("p1", latest_requirements_version=2, core_challenge_ids=set())

    assert freshness["as-is-report-v1"].state == "outdated"


def test_stale_propagates_from_parent_to_child(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="as-is-report", requirements_version=1))
    store.save("p1", _artifact(type="slides", slide_kind="discussion",
                               requirements_version=1, derived_from=["as-is-report-v1"]))
    ManifestStore(storage).save("p1", _manifest(2, "as_is"))

    freshness = store.freshness("p1", latest_requirements_version=2, core_challenge_ids=set())

    assert freshness["slides-v1"].state == "stale"
    assert "as-is-report-v1" in freshness["slides-v1"].reasons[0]


def test_missing_parent_is_reported_as_stale_not_raised(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="as-is-report", requirements_version=1))
    store.save("p1", _artifact(type="slides", slide_kind="discussion",
                               requirements_version=1, derived_from=["as-is-report-v1"]))
    storage.put("projects/p1/artifacts/slides-v1", {
        **storage.get("projects/p1/artifacts/slides-v1"),
        "derived_from": ["as-is-report-v9"],
    })

    freshness = store.freshness("p1", latest_requirements_version=1, core_challenge_ids=set())

    assert freshness["slides-v1"].state == "stale"


def test_uncovered_core_challenge_makes_prfaq_stale(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="mini-prfaq", requirements_version=1,
                               covered_challenge_ids=["ch-1"]))

    freshness = store.freshness("p1", latest_requirements_version=1,
                                core_challenge_ids={"ch-1", "ch-2"})

    assert freshness["mini-prfaq-v1"].state == "stale"
    assert "ch-2" in freshness["mini-prfaq-v1"].reasons[0]


def test_unset_coverage_is_outdated_not_stale(tmp_path):
    """推測によるバックフィルはしない。"""
    storage = LocalJsonStorage(tmp_path)
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="mini-prfaq", requirements_version=1))

    freshness = store.freshness("p1", latest_requirements_version=1,
                                core_challenge_ids={"ch-1"})

    assert freshness["mini-prfaq-v1"].state == "outdated"


def test_coverage_is_ignored_for_non_coverage_types(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    store = ArtifactStore(storage)
    store.save("p1", _artifact(type="as-is-report", requirements_version=1))

    freshness = store.freshness("p1", latest_requirements_version=1,
                                core_challenge_ids={"ch-1"})

    assert freshness["as-is-report-v1"].state == "current"
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_artifacts.py -k freshness -v`
Expected: FAIL — `AttributeError: 'ArtifactStore' object has no attribute 'freshness'`

- [ ] **Step 3: 実装**

`core/src/medo_core/artifacts.py` に追記:

```python
from datetime import date

from medo_core.manifest import ManifestStore, fold_sections, fold_substantive_sections

# 型ごとの依存セクション。生成物側の宣言ではなく core が固定ルールとして持つ。
DEPENDENT_SECTIONS: dict[tuple[str, str | None], tuple[str, ...]] = {
    ("fermi", None): (),
    ("research", None): (),
    ("as-is-report", None): ("as_is", "gaps", "constraints", "stakeholders", "attempts"),
    ("mini-prfaq", None): ("goal", "challenges", "principles", "constraints", "to_be", "kpis"),
    ("prfaq", None): (
        "goal", "challenges", "principles", "constraints", "to_be", "kpis",
        "as_is", "gaps", "bottlenecks", "hypotheses", "attempts", "stakeholders",
    ),
    ("comparison", None): ("challenges", "principles", "constraints", "kpis"),
    ("slides", "discussion"): ("open_questions", "to_be", "kpis"),
    ("slides", "final"): ("open_questions",),
    ("architecture", None): ("functional", "non_functional", "constraints"),
    ("mock", None): ("functional", "constraints"),
}


class Freshness(BaseModel):
    state: Literal["current", "outdated", "stale"] = "current"
    reasons: list[str] = Field(default_factory=list)
    uncovered_challenge_ids: list[str] = Field(default_factory=list)
```

**`uncovered_challenge_ids` を構造化して持つ**。`reasons`(人間向けの文言)を診断側で文字列一致して未カバーを判定すると、文言を変えた瞬間に診断が壊れる。

`ArtifactStore` にメソッドを追加:

```python
    def freshness(
        self,
        project_id: str,
        latest_requirements_version: int,
        core_challenge_ids: set[str],
        *,
        is_citation_stale=None,
        today: date | None = None,
    ) -> dict[str, Freshness]:
        """全生成物の鮮度を、親を再帰評価して返す。

        型ごと最新版のみを保持すると、親が旧版のPRFAQだと解決できないため
        全Artifactを保持して評価する。
        """
        artifacts = self._load_all(project_id)
        manifests = ManifestStore(self._storage).list(project_id)
        resolved: dict[str, Freshness] = {}

        def evaluate(a_id: str, seen: frozenset[str]) -> Freshness:
            if a_id in resolved:
                return resolved[a_id]
            if a_id in seen:
                return Freshness(state="stale", reasons=[f"依存が循環しています: {a_id}"])
            artifact = artifacts.get(a_id)
            if artifact is None:
                return Freshness(state="stale", reasons=[f"親が存在しません: {a_id}"])

            reasons: list[str] = []
            uncovered: list[str] = []
            state = "current"

            stale_citations = (
                is_citation_stale(artifact, today) if is_citation_stale else []
            )
            if stale_citations:
                state = "stale"
                reasons.append(f"引用が古くなっています: {', '.join(stale_citations)}")

            sections = DEPENDENT_SECTIONS.get((artifact.type, artifact.slide_kind), ())
            changed = fold_substantive_sections(
                manifests, from_version=artifact.requirements_version
            )
            hit = sorted(set(sections) & changed)
            if hit:
                state = "stale"
                reasons.append(f"依存セクションが変更されました: {', '.join(hit)}")
            else:
                editorial = sorted(set(sections) & fold_sections(
                    manifests, artifact.requirements_version, "editorial"
                ))
                if editorial:
                    state = "outdated"
                    reasons.append(f"依存セクションの文言が変わりました: {', '.join(editorial)}")

            if artifact.type in COVERAGE_TYPES:
                if artifact.covered_challenge_ids is None:
                    if core_challenge_ids and state == "current":
                        state = "outdated"
                        reasons.append("カバレッジが未宣言のため差分を確認してください")
                else:
                    missing = sorted(core_challenge_ids - set(artifact.covered_challenge_ids))
                    if missing:
                        state = "stale"
                        uncovered = missing
                        reasons.append(f"未対応の課題があります: {', '.join(missing)}")

            for parent_id in artifact.derived_from:
                parent = evaluate(parent_id, seen | {a_id})
                if parent.state == "stale":
                    state = "stale"
                    reasons.append(f"親が古くなっています: {parent_id}")
                elif parent.state == "outdated" and state == "current":
                    state = "outdated"
                    reasons.append(f"親の差分確認が必要です: {parent_id}")

            result = Freshness(
                state=state, reasons=reasons, uncovered_challenge_ids=uncovered
            )
            resolved[a_id] = result
            return result

        return {a_id: evaluate(a_id, frozenset()) for a_id in artifacts}
```

**`is_citation_stale` を注入で受け取る**(`Callable[[Artifact, date | None], list[str]]`)。`ArtifactStore` が `FactStore` / `KnowledgeStore` を直接持つと、生成物ストアが知識層に依存して逆流する([structure.md](../../.claude/steering/structure.md) の依存方向)。既存 `status.py` の `_artifact_stale` が持つファクト・ナリッジの鮮度判定ロジックをこの関数として切り出し、`status.py` 側から渡す。

**注**: `stale_artifacts()` はフェーズ1の `status` が使っているため残す(Task 19で `freshness` へ切り替える)。

追加のテスト:

```python
def test_stale_citation_makes_artifact_stale(tmp_path):
    """researchは要件に依存しないが、引用ファクトの鮮度切れでは陳腐化する。"""
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    store.save("p1", _artifact(type="research", cited_facts=["fact-1"], content="調査"))

    freshness = store.freshness(
        "p1", latest_requirements_version=1, core_challenge_ids=set(),
        is_citation_stale=lambda a, today: list(a.cited_facts),
    )

    assert freshness["research-v1"].state == "stale"
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/ -v`
Expected: 全て pass

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/artifacts.py core/tests/test_artifacts.py
git commit -m "feat(core): セクション依存による陳腐化判定とstale伝播を追加

文書全体を単位にすると、要件に依存しないfermiまで誤検出する。
一方ノード単位の依存追跡だけでは「課題の追加」を取りこぼすため、
セクション単位の判定とカバレッジ判定を併用する。"
```

---

## Task 10: 生成物CLIの拡張

**Files:**
- Modify: `cli/src/medo_cli/main.py`
- Modify: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 8〜9
- Produces: `medo artifacts save --type <t> [--slide-kind discussion|final] [--derived-from <id,...>] [--covers <ch-id,...>]`

- [ ] **Step 1: 失敗するテストを書く**

`cli/tests/test_cli.py` に追記:

```python
def test_artifacts_save_accepts_derived_from_and_slide_kind(tmp_path, runner):
    _save_minimal_requirements(runner, "p1")
    content = tmp_path / "report.md"
    content.write_text("# 現状", encoding="utf-8")
    runner.invoke(app, [
        "artifacts", "save", "--project", "p1", "--type", "as-is-report",
        "--requirements-version", "1", "--generated-by", "claude", "--file", str(content),
    ])
    slides = tmp_path / "slides.md"
    slides.write_text("---\nmarp: true\n---\n# 現状", encoding="utf-8")

    result = runner.invoke(app, [
        "artifacts", "save", "--project", "p1", "--type", "slides",
        "--slide-kind", "discussion", "--derived-from", "as-is-report-v1",
        "--requirements-version", "1", "--generated-by", "gemini", "--file", str(slides),
    ])

    assert result.exit_code == 0
    assert "saved: slides-v1" in result.stdout


def test_artifacts_save_rejects_slides_without_slide_kind(tmp_path, runner):
    _save_minimal_requirements(runner, "p1")
    slides = tmp_path / "slides.md"
    slides.write_text("# x", encoding="utf-8")

    result = runner.invoke(app, [
        "artifacts", "save", "--project", "p1", "--type", "slides",
        "--requirements-version", "1", "--generated-by", "claude", "--file", str(slides),
    ])

    assert result.exit_code == 1
    assert "slide_kind" in result.stderr


def test_artifacts_save_records_covered_challenges(tmp_path, runner):
    _save_minimal_requirements(runner, "p1")
    content = tmp_path / "c.md"
    content.write_text("# 比較", encoding="utf-8")

    result = runner.invoke(app, [
        "artifacts", "save", "--project", "p1", "--type", "comparison",
        "--covers", "ch-1,ch-2", "--requirements-version", "1",
        "--generated-by", "claude", "--file", str(content),
    ])

    assert result.exit_code == 0
```

`_save_minimal_requirements` はテスト内のヘルパー。既存の同等ヘルパーがあればそれを使う。

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest cli/tests/test_cli.py -k artifacts_save -v`
Expected: FAIL — `no such option: --slide-kind`

- [ ] **Step 3: 既存の `artifacts save` にオプションを追加**

**関数を書き換えず、既存シグネチャに引数を足す**。既存の `--cites` / `--cites-facts` / `--options` / `--grown-from` を落とすと、`prfaq`(`grown_from` 必須)がCLIから保存できなくなる。

```python
@artifacts_app.command("save")
def artifacts_save(
    project: str = typer.Option(...),
    artifact_type: str = typer.Option(..., "--type"),
    file: Path = typer.Option(..., exists=True, readable=True),
    cites: str = typer.Option("", help="引用ナレッジエントリID(カンマ区切り)"),
    cites_facts: str = typer.Option("", help="引用ファクトID(カンマ区切り)"),
    options: str = typer.Option("", help="mini-prfaq用: name:approach_type をカンマ区切り"),
    grown_from: str = typer.Option("", help="prfaq用: <mini-prfaq-vN>:<打ち手名>"),
    generated_by: str | None = typer.Option(None),
    requirements_version: int = typer.Option(...),
    # --- ここから追加 ---
    slide_kind: str | None = typer.Option(None, "--slide-kind",
                                          help="slides用: discussion|final"),
    derived_from: str = typer.Option("", "--derived-from",
                                     help="内容依存の親artifact ID(カンマ区切り)"),
    covers: str = typer.Option("", "--covers", help="扱った課題ID(カンマ区切り)"),
    rejected: list[str] = typer.Option(
        [], "--rejected",
        help="見送った案: <名前>:<理由>[:<受け入れたリスク>](複数可)",
    ),
):
```

`Artifact(...)` の生成箇所に4フィールドを足す(既存フィールドはそのまま):

```python
            slide_kind=slide_kind,
            derived_from=[c for c in derived_from.split(",") if c],
            covered_challenge_ids=[c for c in covers.split(",") if c] if covers else None,
            rejected_options=[
                RejectedOption(name=n, reason=r, accepted_risk=risk)
                for n, r, risk in (
                    (*v.split(":", 2), "", "")[:3] for v in rejected
                )
            ],
```

既存の `artifacts save` の引数名・挙動は維持する(追加のみ)。

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest cli/tests/ -v`
Expected: 全て pass

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(cli): 生成物保存に依存・用途・カバレッジを追加

カバレッジは本文の文字列一致やLLM判定で推定せず、保存時に明示的に
宣言させる(数値・事実の通り道にLLMを挟まない原則との整合)。"
```

---

## Task 11: イベント型とEventStore

**Files:**
- Create: `core/src/medo_core/events.py`
- Create: `core/tests/test_events.py`

**Interfaces:**
- Consumes: Task 1〜3 のノード型
- Produces: `ArtifactTarget` / `RequirementsTarget` / `TargetRef` / `WorkflowEventBase` / `CheckRecorded` / `AsIsReportReviewed` / `StakeholderResponded` / `MilestoneDetected` / `ToBeCheckpointRecorded` / `WorkflowEvent`(判別共用体) / `EventStore.append(project_id, event) -> str` / `.list(project_id) -> list[WorkflowEvent]`

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_events.py`:

```python
import pytest
from pydantic import ValidationError

from medo_core.events import (
    ArtifactTarget,
    AsIsReportReviewed,
    CheckRecorded,
    EventStore,
    MilestoneDetected,
    RequirementsTarget,
    StakeholderResponded,
    ToBeCheckpointRecorded,
)
from medo_core.storage import LocalJsonStorage


def _check(**kw) -> CheckRecorded:
    base = {
        "target": RequirementsTarget(version=1),
        "occurred_on": "2026-08-30",
        "requirements_version": 1,
        "round_id": 1,
        "check": "reality_gap",
        "result": "completed",
    }
    base.update(kw)
    return CheckRecorded.model_validate(base)


def test_every_event_carries_round_id():
    """round_id が無いと、反応やチェックがどの周回に属するかを一意に決められず
    round_delta を決定論的に算出できない。"""
    assert _check().round_id == 1


def test_target_ref_is_discriminated_by_kind():
    ev = _check(target=ArtifactTarget(artifact_id="as-is-report-v1"))

    assert ev.target.kind == "artifact"
    assert ev.target.artifact_id == "as-is-report-v1"


def test_undeterminable_requires_note():
    with pytest.raises(ValidationError):
        _check(result="undeterminable")


def test_finding_requires_note_or_refs():
    with pytest.raises(ValidationError):
        _check(result="finding")


def test_undeterminable_defaults_to_open_disposition():
    """扱いを決めずに素通りできないよう、既定は収束をブロックする open。"""
    ev = _check(result="undeterminable", note="組織として方向性が未定")

    assert ev.disposition == "open"


def test_review_requires_findings_when_changes_requested():
    with pytest.raises(ValidationError):
        AsIsReportReviewed(
            target=ArtifactTarget(artifact_id="as-is-report-v1"),
            occurred_on="2026-08-30", requirements_version=1, round_id=1,
            outcome="changes_requested", reviewed_slides_id="slides-v1",
        )


def test_review_accepts_slide_only_findings():
    """スライド固有の差し戻しを要件ノードで表せないため、自由文の枠を持つ。"""
    ev = AsIsReportReviewed(
        target=ArtifactTarget(artifact_id="as-is-report-v1"),
        occurred_on="2026-08-30", requirements_version=1, round_id=1,
        outcome="changes_requested", reviewed_slides_id="slides-v1",
        slide_findings=["見出しが非難調になっている"],
    )

    assert ev.finding_refs == []


def test_append_assigns_monotonic_event_ids(tmp_path):
    store = EventStore(LocalJsonStorage(tmp_path))

    assert store.append("p1", _check()) == "ev-1"
    assert store.append("p1", _check()) == "ev-2"


def test_list_returns_events_in_id_order(tmp_path):
    store = EventStore(LocalJsonStorage(tmp_path))
    for _ in range(11):
        store.append("p1", _check())

    assert [e.id for e in store.list("p1")][:2] == ["ev-1", "ev-2"]
    assert store.list("p1")[-1].id == "ev-11"


def test_events_of_different_kinds_round_trip(tmp_path):
    store = EventStore(LocalJsonStorage(tmp_path))
    store.append("p1", _check())
    store.append("p1", MilestoneDetected(
        target=RequirementsTarget(version=1), occurred_on="2026-08-30",
        requirements_version=1, round_id=1, condition="internal_as_is_first_added",
    ))

    kinds = [e.kind for e in store.list("p1")]
    assert kinds == ["check", "milestone"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_core.events'`

- [ ] **Step 3: 実装**

`core/src/medo_core/events.py`:

```python
"""標準周回の進行記録。

要件の中に置くと論理的に破綻する — 要件は保存のたびに版が進むため、
v3への反応を記録するとその保存自体がv4を作り、記録した瞬間に旧版宛てになる。
したがって要件の版とは独立した追記型イベントとして持つ。
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, model_validator

from medo_core.storage import Storage

CheckName = Literal[
    "source_quality", "reality_gap", "past_attempts", "hidden_stakeholders",
    "decision_maker", "internal_consistency", "as_is_articulation",
    "expression_safety", "to_be_articulation", "feasibility", "scope_agreement",
]

MilestoneCondition = Literal[
    "internal_as_is_first_added",
    "perception_gap_added",
    "internal_conflict_gap_added",
    "constraint_added",
    "stalled_attempt_added",
    "resistant_or_decision_maker_added",
    "review_changes_requested",
    "stakeholder_objected",
    "hypothesis_validated",
    "to_be_confirmed",
]


class ArtifactTarget(BaseModel):
    kind: Literal["artifact"] = "artifact"
    artifact_id: str


class RequirementsTarget(BaseModel):
    kind: Literal["requirements"] = "requirements"
    version: int


TargetRef = Annotated[ArtifactTarget | RequirementsTarget, Field(discriminator="kind")]


def _iso_date(value: str) -> str:
    date.fromisoformat(value)
    return value


IsoDate = Annotated[str, AfterValidator(_iso_date)]


class WorkflowEventBase(BaseModel):
    id: str = ""
    target: TargetRef
    occurred_on: IsoDate
    requirements_version: int
    round_id: int


class CheckRecorded(WorkflowEventBase):
    kind: Literal["check"] = "check"
    check: CheckName
    result: Literal["completed", "finding", "undeterminable"]
    note: str = ""
    finding_refs: list[str] = Field(default_factory=list)
    disposition: Literal["open", "deferred", "promoted"] = "open"

    @model_validator(mode="after")
    def _require_evidence_for_non_completed(self) -> "CheckRecorded":
        if self.result == "undeterminable" and not self.note:
            raise ValueError("undeterminable には note(判断できなかった理由)が必須です")
        if self.result == "finding" and not (self.note or self.finding_refs):
            raise ValueError("finding には note または finding_refs が必須です")
        return self


class AsIsReportReviewed(WorkflowEventBase):
    kind: Literal["asis_review"] = "asis_review"
    outcome: Literal["approved", "changes_requested"]
    finding_refs: list[str] = Field(default_factory=list)
    slide_findings: list[str] = Field(default_factory=list)
    reviewed_slides_id: str
    reviewed_by: Literal["claude", "codex", "gemini", "human"] = "human"

    @model_validator(mode="after")
    def _require_findings_when_changes_requested(self) -> "AsIsReportReviewed":
        if self.outcome == "changes_requested" and not (
            self.finding_refs or self.slide_findings
        ):
            raise ValueError(
                "changes_requested には finding_refs または slide_findings が必須です"
            )
        return self


class StakeholderResponded(WorkflowEventBase):
    kind: Literal["response"] = "response"
    stakeholder_id: str
    purpose: Literal["as_is_alignment", "to_be_go_ahead", "phase_signoff"]
    reaction: Literal["empathized", "acknowledged", "agreed", "objected", "unclear"]
    note: str = ""


class MilestoneDetected(WorkflowEventBase):
    kind: Literal["milestone"] = "milestone"
    condition: MilestoneCondition
    focus_hypothesis_id: str = ""


class ToBeCheckpointRecorded(WorkflowEventBase):
    kind: Literal["tobe_checkpoint"] = "tobe_checkpoint"
    answer: Literal["generate", "defer"]
    responds_to: str


WorkflowEvent = Annotated[
    CheckRecorded
    | AsIsReportReviewed
    | StakeholderResponded
    | MilestoneDetected
    | ToBeCheckpointRecorded,
    Field(discriminator="kind"),
]

_EVENT_TYPES = {
    "check": CheckRecorded,
    "asis_review": AsIsReportReviewed,
    "response": StakeholderResponded,
    "milestone": MilestoneDetected,
    "tobe_checkpoint": ToBeCheckpointRecorded,
}


class EventStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _prefix(self, project_id: str) -> str:
        return f"projects/{project_id}/events"

    def append(self, project_id: str, event) -> str:
        numbers = [
            int(p.rsplit("/ev-", 1)[1]) for p in self._storage.list(self._prefix(project_id))
        ]
        event_id = f"ev-{max(numbers, default=0) + 1}"
        event = event.model_copy(update={"id": event_id})
        self._storage.put(
            f"{self._prefix(project_id)}/{event_id}", event.model_dump(mode="json")
        )
        return event_id

    def list(self, project_id: str) -> list:
        events = [self._storage.get(p) for p in self._storage.list(self._prefix(project_id))]
        parsed = [_EVENT_TYPES[raw["kind"]].model_validate(raw) for raw in events]
        return sorted(parsed, key=lambda e: int(e.id.rsplit("-", 1)[1]))
```

**注**: `list` は `ev-11` が `ev-2` より前に来る文字列順を避けるため、数値でソートする。

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_events.py -v`
Expected: 10 passed

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/events.py core/tests/test_events.py
git commit -m "feat(core): 進行記録のイベントモデルを追加

進行記録を要件内に置くと、記録した瞬間に旧版宛てになり
「現行版への合意」を収束条件にできない。追記型の別ストアに分ける。"
```

---

## Task 12: イベント記録時の整合性検証

**Files:**
- Create: `core/src/medo_core/workflow.py`
- Create: `core/tests/test_workflow.py`

**Interfaces:**
- Consumes: Task 5〜6 の `RequirementsStore`、Task 8 の `ArtifactStore`、Task 11 の `EventStore`
- Produces: `WorkflowRecorder(storage)` / `.record(project_id, event) -> str`(検証・`round_id`採番・`MilestoneDetected` 自動記録を含む)

**注**: 検証は `EventStore` ではなく `WorkflowRecorder` に置く。`EventStore` は要件・生成物を知らない純粋な追記ストアに保ち、他ストアを参照する検証は上位に集約する(`ArtifactStore.save` が Store 側で参照検証しているのと同じ理由)。

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_workflow.py`:

```python
import json
from datetime import date

import pytest

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.events import (
    ArtifactTarget,
    AsIsReportReviewed,
    CheckRecorded,
    EventStore,
    MilestoneDetected,
    RequirementsTarget,
    StakeholderResponded,
    ToBeCheckpointRecorded,
)
from medo_core.nodes import AsIs, Stakeholder
from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.storage import LocalJsonStorage
from medo_core.workflow import WorkflowRecorder

TODAY = "2026-08-30"          # イベントの occurred_on(ISO文字列)
TODAY_DATE = date(2026, 8, 30)  # 要件保存の today(date型)


@pytest.fixture
def project(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    reqs = RequirementsStore(storage)
    reqs.save("p1", RequirementsDoc(
        project="p1",
        as_is=[AsIs(text="紙の伝票を手入力", visibility="internal")],
        stakeholders=[Stakeholder(text="情報システム部長", is_decision_maker=True)],
    ))
    return storage


def _recorder(storage) -> WorkflowRecorder:
    return WorkflowRecorder(storage)


def test_record_assigns_round_id_from_requirements_history(project):
    ev_id = _recorder(project).record("p1", CheckRecorded(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, check="reality_gap", result="completed",
    ))

    stored = EventStore(project).list("p1")[0]
    assert stored.id == ev_id
    assert stored.round_id == 0


def test_record_rejects_target_pointing_to_nonexistent_version(project):
    """存在しない版を対象にすると、畳み込みの祖先判定が壊れる。"""
    with pytest.raises(ValueError, match="v9"):
        _recorder(project).record("p1", CheckRecorded(
            target=RequirementsTarget(version=9), occurred_on=TODAY,
            requirements_version=1, round_id=0, check="reality_gap", result="completed",
        ))


def test_record_rejects_response_for_unknown_stakeholder(project):
    ArtifactStore(project).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))

    with pytest.raises(ValueError, match="sh-99"):
        _recorder(project).record("p1", StakeholderResponded(
            target=ArtifactTarget(artifact_id="as-is-report-v1"), occurred_on=TODAY,
            requirements_version=1, round_id=0,
            stakeholder_id="sh-99", purpose="as_is_alignment", reaction="agreed",
        ))


def test_record_rejects_purpose_target_mismatch(project):
    """to_be_go_ahead は要件を対象にする。生成物宛てを許すと畳み込みが壊れる。"""
    ArtifactStore(project).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))

    with pytest.raises(ValueError, match="to_be_go_ahead"):
        _recorder(project).record("p1", StakeholderResponded(
            target=ArtifactTarget(artifact_id="as-is-report-v1"), occurred_on=TODAY,
            requirements_version=1, round_id=0,
            stakeholder_id="sh-1", purpose="to_be_go_ahead", reaction="agreed",
        ))


def test_record_rejects_review_of_non_report_artifact(project):
    ArtifactStore(project).save("p1", Artifact(
        project="p1", type="research", requirements_version=1,
        generated_by="claude", content="調査",
    ))

    with pytest.raises(ValueError, match="as-is-report"):
        _recorder(project).record("p1", AsIsReportReviewed(
            target=ArtifactTarget(artifact_id="research-v1"), occurred_on=TODAY,
            requirements_version=1, round_id=0, outcome="approved",
            reviewed_slides_id="slides-v1",
        ))


def test_record_requires_reviewed_slides_derived_from_the_report(project):
    """レポートとスライドを必ず一緒にレビューする契約と整合させる。"""
    store = ArtifactStore(project)
    store.save("p1", Artifact(project="p1", type="as-is-report", requirements_version=1,
                              generated_by="claude", content="# 現状"))
    store.save("p1", Artifact(project="p1", type="research", requirements_version=1,
                              generated_by="claude", content="調査"))

    with pytest.raises(ValueError, match="reviewed_slides_id"):
        _recorder(project).record("p1", AsIsReportReviewed(
            target=ArtifactTarget(artifact_id="as-is-report-v1"), occurred_on=TODAY,
            requirements_version=1, round_id=0, outcome="approved",
            reviewed_slides_id="research-v1",
        ))


def test_record_rejects_double_answer_to_same_milestone(project):
    rec = _recorder(project)
    ms_id = rec.record("p1", MilestoneDetected(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, condition="constraint_added",
    ))
    rec.record("p1", ToBeCheckpointRecorded(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, answer="generate", responds_to=ms_id,
    ))

    with pytest.raises(ValueError, match="回答済み"):
        rec.record("p1", ToBeCheckpointRecorded(
            target=RequirementsTarget(version=1), occurred_on=TODAY,
            requirements_version=1, round_id=0, answer="defer", responds_to=ms_id,
        ))


def test_record_deduplicates_milestone_by_version_and_condition(project):
    """要件保存後のイベント記録失敗に備え、再試行しても重複しない。"""
    rec = _recorder(project)
    first = rec.record("p1", MilestoneDetected(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, condition="constraint_added",
    ))
    second = rec.record("p1", MilestoneDetected(
        target=RequirementsTarget(version=1), occurred_on=TODAY,
        requirements_version=1, round_id=0, condition="constraint_added",
    ))

    assert first == second
    assert len(EventStore(project).list("p1")) == 1


def test_objection_records_milestone_automatically(project):
    """条件8は要件保存を伴わずに発生するため、イベント記録自体が節目を作る。"""
    ArtifactStore(project).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=1,
        generated_by="claude", content="# 現状",
    ))
    rec = _recorder(project)
    rec.record("p1", StakeholderResponded(
        target=ArtifactTarget(artifact_id="as-is-report-v1"), occurred_on=TODAY,
        requirements_version=1, round_id=0,
        stakeholder_id="sh-1", purpose="as_is_alignment", reaction="objected",
    ))

    conditions = [e.condition for e in EventStore(project).list("p1") if e.kind == "milestone"]
    assert conditions == ["stakeholder_objected"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_workflow.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_core.workflow'`

- [ ] **Step 3: 実装**

`core/src/medo_core/workflow.py`:

```python
"""イベント記録の入口。他ストアを参照する検証と節目の自動記録を集約する。

EventStore は要件・生成物を知らない純粋な追記ストアに保つ。
"""

from medo_core.artifacts import ArtifactStore
from medo_core.events import (
    AsIsReportReviewed,
    CheckRecorded,
    EventStore,
    MilestoneDetected,
    StakeholderResponded,
    ToBeCheckpointRecorded,
)
from medo_core.requirements import RequirementsStore
from medo_core.storage import Storage

# purpose → (許容するtarget種別, 生成物の場合の許容type, slide_kind)
PURPOSE_TARGETS = {
    "as_is_alignment": ("artifact", "as-is-report", None),
    "to_be_go_ahead": ("requirements", None, None),
    "phase_signoff": ("artifact", "slides", "final"),
}

EVENT_TARGET_KIND = {
    "asis_review": "artifact",
    "milestone": "requirements",
    "tobe_checkpoint": "requirements",
}


class WorkflowRecorder:
    def __init__(self, storage: Storage):
        self._events = EventStore(storage)
        self._artifacts = ArtifactStore(storage)
        self._requirements = RequirementsStore(storage)

    def record(self, project_id: str, event) -> str:
        existing = self._events.list(project_id)
        duplicate = self._find_duplicate_milestone(event, existing)
        if duplicate:
            return duplicate

        self._validate_target_kind(project_id, event)
        self._validate_references(project_id, event, existing)
        event = event.model_copy(
            update={"round_id": self.round_count(project_id)}
        )
        event_id = self._events.append(project_id, event)
        self._record_event_driven_milestone(project_id, event)
        return event_id

    def _validate_cross_store_refs(self, project_id: str, doc: RequirementsDoc) -> None:
        """生成物・イベントを参照するフィールドの実在を検証する。"""
        event_ids = {e.id for e in self._events.list(project_id)}
        undeterminable_ids = {
            e.id for e in self._events.list(project_id)
            if e.kind == "check" and e.result == "undeterminable"
        }

        for tb in doc.to_be:
            for ref in tb.evidenced_by:
                if ref.startswith("ev-") and ref not in event_ids:
                    raise ValueError(f"evidenced_by のイベントが存在しません: {ref}")

        for ch in doc.challenges:
            src = ch.promoted_from
            if src and src.kind == "undeterminable" and src.ref not in undeterminable_ids:
                raise ValueError(
                    "promoted_from(undeterminable)の参照先は result='undeterminable' の"
                    f"CheckRecorded である必要があります: {src.ref}"
                )

        for hyp in doc.hypotheses:
            if hyp.fermi_ref is None:
                continue
            artifact = self._artifacts.get(project_id, hyp.fermi_ref.artifact_id)
            if artifact is None or artifact.type != "fermi":
                raise ValueError(
                    f"fermi_ref の参照先が fermi ではありません: "
                    f"{hyp.fermi_ref.artifact_id}"
                )
            if hyp.fermi_ref.variable_name not in _fermi_variables(artifact):
                raise ValueError(
                    "fermi_ref の変数がモデルに存在しません: "
                    f"{hyp.fermi_ref.variable_name}"
                )

    def round_count(self, project_id: str) -> int:
        """要件履歴を走査し、as_is変更のあと to_be変更が現れたら1周と数える。"""
        from medo_core.manifest import ManifestStore

        round_id = 0
        state = "waiting_as_is"
        for m in ManifestStore(self._requirements._storage).list(project_id):
            sections = {c.section for c in m.changes if c.change_kind == "substantive"}
            if not sections:
                continue
            if state == "waiting_as_is" and "as_is" in sections:
                state = "waiting_to_be"
            if state == "waiting_to_be" and "to_be" in sections:
                round_id += 1
                state = "waiting_as_is"
        return round_id
```

検証の各メソッド:

```python
    def _find_duplicate_milestone(self, event, existing: list) -> str | None:
        if event.kind != "milestone":
            return None
        for e in existing:
            if (
                e.kind == "milestone"
                and e.requirements_version == event.requirements_version
                and e.condition == event.condition
            ):
                return e.id
        return None

    def _validate_target_kind(self, project_id: str, event) -> None:
        expected = EVENT_TARGET_KIND.get(event.kind)
        if expected and event.target.kind != expected:
            raise ValueError(
                f"{event.kind} の target は {expected} である必要があります"
            )
        if event.target.kind == "requirements":
            latest = self._requirements.latest_version(project_id)
            if not 1 <= event.target.version <= latest:
                raise ValueError(
                    f"要件バージョンが存在しません: v{event.target.version}"
                    f"(最新: v{latest})"
                )
        if event.kind == "response":
            kind, artifact_type, slide_kind = PURPOSE_TARGETS[event.purpose]
            if event.target.kind != kind:
                raise ValueError(
                    f"purpose={event.purpose} の target は {kind} である必要があります"
                )

    def _validate_references(self, project_id: str, event, existing: list) -> None:
        if isinstance(event, StakeholderResponded):
            self._validate_response(project_id, event)
        elif isinstance(event, AsIsReportReviewed):
            self._validate_review(project_id, event)
        elif isinstance(event, ToBeCheckpointRecorded):
            self._validate_checkpoint(event, existing)
        elif isinstance(event, CheckRecorded):
            self._validate_check(project_id, event)
        elif isinstance(event, MilestoneDetected) and event.focus_hypothesis_id:
            self._validate_hypothesis(project_id, event.focus_hypothesis_id)

    def _validate_check(self, project_id: str, event: CheckRecorded) -> None:
        """artifact束縛のcheckは、registryが定める型の生成物だけを対象にできる。"""
        from medo_core.checks import CHECK_REGISTRY

        spec = CHECK_REGISTRY[event.check]
        if spec.binding != "artifact_bound":
            if event.target.kind != "requirements":
                raise ValueError(f"{event.check} の target は requirements です")
            return
        if event.target.kind != "artifact":
            raise ValueError(f"{event.check} の target は artifact です")
        artifact = self._artifacts.get(project_id, event.target.artifact_id)
        if artifact is None or artifact.type != spec.target_type or (
            spec.slide_kind and artifact.slide_kind != spec.slide_kind
        ):
            raise ValueError(
                f"{event.check} の対象は {spec.target_type} である必要があります: "
                f"{event.target.artifact_id}"
            )

    def _validate_hypothesis(self, project_id: str, hypothesis_id: str) -> None:
        doc = self._requirements.get(project_id)
        if not doc or hypothesis_id not in {h.id for h in doc.hypotheses}:
            raise ValueError(f"仮説が存在しません: {hypothesis_id}")

    def _validate_response(self, project_id: str, event: StakeholderResponded) -> None:
        doc = self._requirements.get(project_id)
        if not doc or event.stakeholder_id not in {s.id for s in doc.stakeholders}:
            raise ValueError(f"stakeholder が存在しません: {event.stakeholder_id}")
        _, artifact_type, slide_kind = PURPOSE_TARGETS[event.purpose]
        if artifact_type is None:
            return
        artifact = self._artifacts.get(project_id, event.target.artifact_id)
        if artifact is None:
            raise ValueError(f"生成物が存在しません: {event.target.artifact_id}")
        if artifact.type != artifact_type or (
            slide_kind and artifact.slide_kind != slide_kind
        ):
            raise ValueError(
                f"purpose={event.purpose} の対象は {artifact_type}"
                f"{f'({slide_kind})' if slide_kind else ''} である必要があります"
            )

    def _validate_review(self, project_id: str, event: AsIsReportReviewed) -> None:
        report = self._artifacts.get(project_id, event.target.artifact_id)
        if report is None or report.type != "as-is-report":
            raise ValueError(
                f"レビュー対象は as-is-report である必要があります: {event.target.artifact_id}"
            )
        slides = self._artifacts.get(project_id, event.reviewed_slides_id)
        if (
            slides is None
            or slides.slide_kind != "discussion"
            or event.target.artifact_id not in slides.derived_from
        ):
            raise ValueError(
                "reviewed_slides_id は当該レポートから生成された討議用スライドである"
                f"必要があります: {event.reviewed_slides_id}"
            )
        doc = self._requirements.get(project_id)
        known = {
            n.id
            for section in ("gaps", "challenges", "open_questions")
            for n in getattr(doc, section)
        } if doc else set()
        for ref in event.finding_refs:
            if ref not in known:
                raise ValueError(f"所見の参照先が存在しません: {ref}")

    def _validate_checkpoint(self, event: ToBeCheckpointRecorded, existing: list) -> None:
        milestones = {e.id for e in existing if e.kind == "milestone"}
        if event.responds_to not in milestones:
            raise ValueError(f"節目イベントが存在しません: {event.responds_to}")
        answered = {
            e.responds_to for e in existing if e.kind == "tobe_checkpoint"
        }
        if event.responds_to in answered:
            raise ValueError(f"回答済みの節目です: {event.responds_to}")

    def _record_event_driven_milestone(self, project_id: str, event) -> None:
        """条件7・8。要件保存を伴わずに発生する節目。"""
        condition = None
        if isinstance(event, AsIsReportReviewed) and event.outcome == "changes_requested":
            condition = "review_changes_requested"
        elif isinstance(event, StakeholderResponded) and event.reaction == "objected":
            condition = "stakeholder_objected"
        if condition is None:
            return
        from medo_core.events import RequirementsTarget

        self.record(project_id, MilestoneDetected(
            target=RequirementsTarget(version=event.requirements_version),
            occurred_on=event.occurred_on,
            requirements_version=event.requirements_version,
            round_id=event.round_id,
            condition=condition,
        ))
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_workflow.py -v`
Expected: 8 passed

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/workflow.py core/tests/test_workflow.py
git commit -m "feat(core): イベント記録の整合性検証と節目の自動記録を追加

節目の検出自体をイベントにする。未回答状態を「対応する回答を持たない
MilestoneDetected」として一意に導けるようにするため。"
```

---

## Task 13: 要件保存による節目の検出

**Files:**
- Modify: `core/src/medo_core/workflow.py`
- Modify: `core/tests/test_workflow.py`

**Interfaces:**
- Consumes: Task 12 の `WorkflowRecorder`
- Produces: `WorkflowRecorder.save_requirements(project_id, doc, *, editorial_sections=(), today=None) -> int`(要件保存 + 節目判定を1操作にまとめる)、`detect_milestone(previous, saved) -> str | None`

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_workflow.py` に追記:

```python
from medo_core.nodes import Attempt, Constraint, Gap, Hypothesis, ToBe
from medo_core.workflow import detect_milestone


def _saved(storage, **kw) -> int:
    doc = RequirementsDoc(project="p1", **kw)
    return WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)


def test_detects_first_internal_as_is(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    _saved(storage, as_is=[AsIs(text="公表", visibility="public")])
    doc = RequirementsStore(storage).get("p1")
    doc.as_is.append(AsIs(text="実は手作業", visibility="internal"))
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["internal_as_is_first_added"]


def test_detects_new_constraint(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    _saved(storage)
    doc = RequirementsStore(storage).get("p1")
    doc.constraints.append(Constraint(text="親会社の内規で外部SaaS禁止"))
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["constraint_added"]


def test_detects_stalled_attempt(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    _saved(storage)
    doc = RequirementsStore(storage).get("p1")
    doc.attempts.append(Attempt(description="RPA導入", outcome="stalled",
                                blocker="情シスが反対"))
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["stalled_attempt_added"]


def test_detects_to_be_promoted_to_confirmed(tmp_path):
    """順調に進んで案が固まったときも等しく重大な分岐点である。"""
    storage = LocalJsonStorage(tmp_path)
    _saved(storage, to_be=[ToBe(text="自動化されている", confidence="assumed")])
    doc = RequirementsStore(storage).get("p1")
    doc.to_be[0] = doc.to_be[0].model_copy(update={"confidence": "confirmed"})
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["to_be_confirmed"]


def test_detects_hypothesis_validated(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    _saved(storage, hypotheses=[Hypothesis(kind="cause", statement="承認階層が原因")])
    doc = RequirementsStore(storage).get("p1")
    doc.hypotheses[0] = doc.hypotheses[0].model_copy(update={"status": "validated"})
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    conditions = [e.condition for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert conditions == ["hypothesis_validated"]


def test_records_only_one_milestone_when_several_conditions_hold(tmp_path):
    """1回の保存に対して問いかけは1回でよい。"""
    storage = LocalJsonStorage(tmp_path)
    _saved(storage)
    doc = RequirementsStore(storage).get("p1")
    doc.as_is.append(AsIs(text="実は手作業", visibility="internal"))
    doc.constraints.append(Constraint(text="予算300万円"))
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    milestones = [e for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert len(milestones) == 1
    assert milestones[0].condition == "internal_as_is_first_added"


def test_text_only_edit_is_not_a_milestone(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    _saved(storage, as_is=[AsIs(text="手作業", visibility="internal")])
    doc = RequirementsStore(storage).get("p1")
    doc.as_is[0] = doc.as_is[0].model_copy(update={"text": "紙の伝票を手入力"})
    WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)

    milestones = [e for e in EventStore(storage).list("p1") if e.kind == "milestone"]
    assert milestones == []


def test_save_requirements_rejects_fermi_ref_to_missing_variable(tmp_path):
    """数値の接続点が壊れていると、感度分析が別の変数を指すまま通ってしまう。"""
    from medo_core.nodes import FermiRef, Hypothesis

    storage = LocalJsonStorage(tmp_path)
    ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="fermi", requirements_version=1,
        content=json.dumps({
            "model": {"name": "工数", "formula": "transcription_hours * 12",
                      "variables": {"transcription_hours": {"assume": 120}}},
            "result": {"name": "工数", "value": 1440, "resolved": {}},
        }),
    ))
    doc = RequirementsDoc(project="p1", hypotheses=[Hypothesis(
        kind="impact", statement="半減する",
        fermi_ref=FermiRef(artifact_id="fermi-v1", variable_name="unknown_var"),
    )])

    with pytest.raises(ValueError, match="unknown_var"):
        WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)


def test_save_requirements_rejects_promotion_from_non_undeterminable_event(tmp_path):
    from medo_core.nodes import Challenge, PromotionSource

    storage = LocalJsonStorage(tmp_path)
    doc = RequirementsDoc(project="p1", challenges=[Challenge(
        text="方向性が定まっていない",
        promoted_from=PromotionSource(kind="undeterminable", ref="ev-99"),
    )])

    with pytest.raises(ValueError, match="ev-99"):
        WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)


def test_save_requirements_rejects_evidenced_by_to_missing_event(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    doc = RequirementsDoc(project="p1",
                          to_be=[ToBe(text="自動化", evidenced_by=["ev-99"])])

    with pytest.raises(ValueError, match="ev-99"):
        WorkflowRecorder(storage).save_requirements("p1", doc, today=TODAY_DATE)


def test_detect_milestone_fires_on_first_save_with_internal_as_is():
    """「0件→1件以上」は初回保存でも成立する。"""
    saved = RequirementsDoc(project="p1",
                            as_is=[AsIs(id="as-1", text="実態", visibility="internal")])

    assert detect_milestone(None, saved) == "internal_as_is_first_added"


def test_detect_milestone_returns_none_for_empty_first_save():
    assert detect_milestone(None, RequirementsDoc(project="p1")) is None
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_workflow.py -k milestone -v`
Expected: FAIL — `AttributeError: 'WorkflowRecorder' object has no attribute 'save_requirements'`

- [ ] **Step 3: 実装**

`core/src/medo_core/workflow.py` に追記:

```python
from datetime import date

from medo_core.requirements import RequirementsDoc


def _fermi_variables(artifact) -> set[str]:
    """fermi生成物のモデル変数名。

    content は `{"model": {...}, "result": {...}}` のJSON
    (cli/src/medo_cli/main.py の fermi calc が書く形式)。
    """
    import json

    payload = json.loads(artifact.content)
    return set((payload.get("model", {}).get("variables") or {}).keys())


def detect_milestone(
    previous: RequirementsDoc | None, saved: RequirementsDoc
) -> str | None:
    """要件保存による節目条件(1〜6・9・10)を、最初に成立したもの1件だけ返す。

    単なる本文の微修正や既存項目の言い換えは節目にしない。
    """
    previous = previous or RequirementsDoc(project=saved.project)

    def new_ids(section: str) -> set[str]:
        old = {n.id for n in getattr(previous, section)}
        return {n.id for n in getattr(saved, section)} - old

    if not [a for a in previous.as_is if a.visibility == "internal"] and [
        a for a in saved.as_is if a.visibility == "internal"
    ]:
        return "internal_as_is_first_added"

    added_gaps = [g for g in saved.gaps if g.id in new_ids("gaps")]
    if any(g.kind == "perception" for g in added_gaps):
        return "perception_gap_added"
    if any(g.kind == "internal_conflict" for g in added_gaps):
        return "internal_conflict_gap_added"

    if new_ids("constraints"):
        return "constraint_added"

    added_attempts = [a for a in saved.attempts if a.id in new_ids("attempts")]
    if any(a.outcome in ("stalled", "failed") for a in added_attempts):
        return "stalled_attempt_added"

    added_stakeholders = [s for s in saved.stakeholders if s.id in new_ids("stakeholders")]
    if any(s.stance == "resistant" or s.is_decision_maker for s in added_stakeholders):
        return "resistant_or_decision_maker_added"

    old_hyp = {h.id: h.status for h in previous.hypotheses}
    if any(
        h.status == "validated" and old_hyp.get(h.id) not in (None, "validated")
        for h in saved.hypotheses
    ):
        return "hypothesis_validated"

    old_to_be = {t.id: t.confidence for t in previous.to_be}
    if any(
        t.confidence == "confirmed" and old_to_be.get(t.id) not in (None, "confirmed")
        for t in saved.to_be
    ):
        return "to_be_confirmed"

    return None
```

`WorkflowRecorder` にメソッドを追加:

```python
    def save_requirements(
        self,
        project_id: str,
        doc: RequirementsDoc,
        *,
        editorial_sections: tuple[str, ...] = (),
        today: date | None = None,
    ) -> int:
        """要件を保存し、節目条件が成立していれば MilestoneDetected を記録する。

        他ストア(生成物・イベント)を参照する検証もここで行う。
        RequirementsStore にそれらを持たせると依存が逆流するため。
        """
        self._validate_cross_store_refs(project_id, doc)
        previous = self._requirements.get(project_id)
        version = self._requirements.save(
            project_id, doc, editorial_sections=editorial_sections, today=today
        )
        saved = self._requirements.get(project_id, version)
        condition = detect_milestone(previous, saved)
        if condition:
            from medo_core.events import RequirementsTarget

            self.record(project_id, MilestoneDetected(
                target=RequirementsTarget(version=version),
                occurred_on=(today or date.today()).isoformat(),
                requirements_version=version,
                round_id=0,
                condition=condition,
            ))
        return version
```

**注**: `record` が `round_id` を再計算するため、呼び出し側の `round_id=0` は捨てられる。

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/ -v`
Expected: 全て pass

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/workflow.py core/tests/test_workflow.py
git commit -m "feat(core): 要件保存による節目条件の判定を追加

節目を「現実が押し返した瞬間」だけに限定すると、仮説が支持されて
案が固まる場合にトリガーが作られない。前進側の条件も対称に持つ。"
```

---

## Task 14: 反応の畳み込み

**Files:**
- Create: `core/src/medo_core/responses.py`
- Create: `core/tests/test_responses.py`

**Interfaces:**
- Consumes: Task 4 の `ChangeManifest`、Task 8 の `Artifact`、Task 11 のイベント型
- Produces: `ConvergenceTarget(requirements_version, as_is_report_id)` / `resolve_convergence_target(doc_version, artifacts) -> ConvergenceTarget` / `EffectiveResponse(stakeholder_id, purpose, reaction, event_id, subsumed_by, expired)` / `fold_responses(events, target, artifacts, manifests) -> list[EffectiveResponse]`

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_responses.py`:

```python
from medo_core.artifacts import Artifact
from medo_core.events import ArtifactTarget, RequirementsTarget, StakeholderResponded
from medo_core.manifest import ChangeManifest, SectionChange
from medo_core.responses import (
    ConvergenceTarget,
    fold_responses,
    resolve_convergence_target,
)


def _artifact(a_id: str, requirements_version: int, type_="as-is-report") -> Artifact:
    version = int(a_id.rsplit("-v", 1)[1])
    return Artifact(project="p1", type=type_, version=version,
                    requirements_version=requirements_version,
                    generated_by="claude", content="x")


def _response(ev_id, stakeholder, purpose, reaction, target, round_id=1):
    ev = StakeholderResponded(
        target=target, occurred_on="2026-08-30", requirements_version=1,
        round_id=round_id, stakeholder_id=stakeholder, purpose=purpose, reaction=reaction,
    )
    return ev.model_copy(update={"id": ev_id})


def _manifest(version, *sections):
    return ChangeManifest(
        version=version,
        changes=[SectionChange(section=s) for s in sections],
        recorded_on="2026-08-30",
    )


def test_convergence_target_picks_report_generated_from_latest_version():
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1),
                 "as-is-report-v2": _artifact("as-is-report-v2", 2)}

    target = resolve_convergence_target(2, artifacts)

    assert target == ConvergenceTarget(requirements_version=2,
                                       as_is_report_id="as-is-report-v2")


def test_convergence_target_is_none_when_no_report_from_latest_version():
    """古い要件から作られたレポートを現在対象にすると両者が食い違う。"""
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1)}

    assert resolve_convergence_target(2, artifacts).as_is_report_id is None


def test_response_to_ancestor_is_superseded_by_response_to_current_target():
    """v1で異議が出た後にv2で修正して合意を得ても、v1の異議が永久に残ってはならない。"""
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1),
                 "as-is-report-v2": _artifact("as-is-report-v2", 2)}
    events = [
        _response("ev-1", "sh-1", "as_is_alignment", "objected",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
        _response("ev-2", "sh-1", "as_is_alignment", "agreed",
                  ArtifactTarget(artifact_id="as-is-report-v2")),
    ]

    effective = fold_responses(events, resolve_convergence_target(2, artifacts),
                               artifacts, manifests=[])

    assert [(e.stakeholder_id, e.reaction, e.event_id) for e in effective] == [
        ("sh-1", "agreed", "ev-2")
    ]


def test_current_target_response_wins_over_later_recorded_ancestor_response():
    """記録の順序ではなく対象の新しさで優先する。"""
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1),
                 "as-is-report-v2": _artifact("as-is-report-v2", 2)}
    events = [
        _response("ev-1", "sh-1", "as_is_alignment", "agreed",
                  ArtifactTarget(artifact_id="as-is-report-v2")),
        _response("ev-2", "sh-1", "as_is_alignment", "objected",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
    ]

    effective = fold_responses(events, resolve_convergence_target(2, artifacts),
                               artifacts, manifests=[])

    assert effective[0].event_id == "ev-1"


def test_ancestor_agreement_expires_when_its_own_sections_change():
    events = [_response("ev-1", "sh-1", "to_be_go_ahead", "agreed",
                        RequirementsTarget(version=1))]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=2, as_is_report_id=None),
                               artifacts={}, manifests=[_manifest(2, "to_be")])

    assert effective[0].expired is True


def test_ancestor_agreement_survives_unrelated_section_change():
    """無関係なconstraints追記で合意が巻き添え失効すると収束不能ループに陥る。"""
    events = [_response("ev-1", "sh-1", "to_be_go_ahead", "agreed",
                        RequirementsTarget(version=1))]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=2, as_is_report_id=None),
                               artifacts={}, manifests=[_manifest(2, "constraints")])

    assert effective[0].expired is False


def test_objection_survives_content_change():
    """解消が確認できるまで残す。安全側に倒す。"""
    events = [_response("ev-1", "sh-1", "to_be_go_ahead", "objected",
                        RequirementsTarget(version=1))]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=2, as_is_report_id=None),
                               artifacts={}, manifests=[_manifest(2, "to_be")])

    assert effective[0].expired is False


def test_higher_purpose_agreement_subsumes_lower_purpose_objection():
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1)}
    events = [
        _response("ev-1", "sh-1", "as_is_alignment", "objected",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
        _response("ev-2", "sh-1", "to_be_go_ahead", "agreed",
                  RequirementsTarget(version=1)),
    ]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=1,
                                                 as_is_report_id="as-is-report-v1"),
                               artifacts, manifests=[])

    objection = next(e for e in effective if e.purpose == "as_is_alignment")
    assert objection.subsumed_by == "ev-2"


def test_responses_of_different_stakeholders_are_folded_independently():
    artifacts = {"as-is-report-v1": _artifact("as-is-report-v1", 1)}
    events = [
        _response("ev-1", "sh-1", "as_is_alignment", "agreed",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
        _response("ev-2", "sh-2", "as_is_alignment", "objected",
                  ArtifactTarget(artifact_id="as-is-report-v1")),
    ]

    effective = fold_responses(events,
                               ConvergenceTarget(requirements_version=1,
                                                 as_is_report_id="as-is-report-v1"),
                               artifacts, manifests=[])

    assert len(effective) == 2
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_responses.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_core.responses'`

- [ ] **Step 3: 実装**

`core/src/medo_core/responses.py`:

```python
"""ステークホルダーの反応の畳み込み。

収束判定は「現在の対象」に対してのみ行う。これが無いと、旧版への異議で
永久に止まり、逆に古い版への合意で誤って通る。
"""

from pydantic import BaseModel

from medo_core.artifacts import Artifact
from medo_core.manifest import ChangeManifest, fold_substantive_sections

PURPOSE_ORDER = {"as_is_alignment": 0, "to_be_go_ahead": 1, "phase_signoff": 2}

# purpose → その合意が依存するセクション。実質変更があれば祖先への合意は失効する。
EXPIRY_SECTIONS = {
    "as_is_alignment": ("as_is", "gaps", "constraints", "stakeholders", "attempts"),
    "to_be_go_ahead": ("to_be", "kpis", "goal"),
    "phase_signoff": (
        "goal", "challenges", "principles", "constraints", "to_be", "kpis",
        "as_is", "gaps", "bottlenecks", "hypotheses", "attempts", "stakeholders",
        "open_questions",
    ),
}


class ConvergenceTarget(BaseModel):
    requirements_version: int
    as_is_report_id: str | None = None
    final_slides_id: str | None = None


class EffectiveResponse(BaseModel):
    stakeholder_id: str
    purpose: str
    reaction: str
    event_id: str
    subsumed_by: str | None = None
    expired: bool = False


def resolve_convergence_target(
    latest_requirements_version: int, artifacts: dict[str, Artifact]
) -> ConvergenceTarget:
    """最新要件版から生成された最新の as-is-report を現在対象とする。"""
    candidates = [
        a_id
        for a_id, a in artifacts.items()
        if a.type == "as-is-report"
        and a.requirements_version == latest_requirements_version
    ]
    newest = max(candidates, key=lambda a_id: artifacts[a_id].version, default=None)
    final_slides = [
        a_id for a_id, a in artifacts.items()
        if a.type == "slides" and a.slide_kind == "final"
    ]
    return ConvergenceTarget(
        requirements_version=latest_requirements_version,
        as_is_report_id=newest,
        final_slides_id=max(
            final_slides, key=lambda a_id: artifacts[a_id].version, default=None
        ),
    )


def _target_version(event, artifacts: dict[str, Artifact]) -> int | None:
    if event.target.kind == "requirements":
        return event.target.version
    artifact = artifacts.get(event.target.artifact_id)
    return artifact.requirements_version if artifact else None


def _is_current(event, target: ConvergenceTarget) -> bool:
    """purpose ごとに現在対象の種別が違う。phase_signoff は最終提案スライド宛て。"""
    if event.target.kind == "requirements":
        return event.target.version == target.requirements_version
    current = (
        target.final_slides_id if event.purpose == "phase_signoff"
        else target.as_is_report_id
    )
    return event.target.artifact_id == current


def fold_responses(
    events: list,
    target: ConvergenceTarget,
    artifacts: dict[str, Artifact],
    manifests: list[ChangeManifest],
) -> list[EffectiveResponse]:
    """(stakeholder_id, purpose) ごとに有効な反応を1件選ぶ。

    現行版への反応を祖先への反応より常に優先する。祖先全体から単純に id 順で
    選ぶと、旧版の反応を後から追記したときに現行版の反応を上書きしてしまう。
    """
    responses = [e for e in events if e.kind == "response"]
    grouped: dict[tuple[str, str], list] = {}
    for e in responses:
        version = _target_version(e, artifacts)
        if version is None or version > target.requirements_version:
            continue
        grouped.setdefault((e.stakeholder_id, e.purpose), []).append(e)

    effective: list[EffectiveResponse] = []
    for (stakeholder_id, purpose), group in grouped.items():
        current = [e for e in group if _is_current(e, target)]
        pool = current or group
        chosen = max(
            pool,
            key=lambda e: (
                _target_version(e, artifacts),
                int(e.id.rsplit("-", 1)[1]),
            ),
        )
        expired = False
        if not current and chosen.reaction in ("agreed", "empathized"):
            changed = fold_substantive_sections(
                manifests, from_version=_target_version(chosen, artifacts)
            )
            expired = bool(set(EXPIRY_SECTIONS[purpose]) & changed)
        effective.append(EffectiveResponse(
            stakeholder_id=stakeholder_id, purpose=purpose,
            reaction=chosen.reaction, event_id=chosen.id, expired=expired,
        ))

    return _apply_subsumption(effective)


def _apply_subsumption(effective: list[EffectiveResponse]) -> list[EffectiveResponse]:
    """上位の purpose での合意は、下位の未解決な異議を包括解消する。"""
    agreed_ranks = {
        e.stakeholder_id: max(
            (PURPOSE_ORDER[x.purpose], x.event_id)
            for x in effective
            if x.stakeholder_id == e.stakeholder_id
            and x.reaction == "agreed"
            and not x.expired
        )
        for e in effective
        if any(
            x.stakeholder_id == e.stakeholder_id and x.reaction == "agreed" and not x.expired
            for x in effective
        )
    }
    result = []
    for e in effective:
        top = agreed_ranks.get(e.stakeholder_id)
        if e.reaction == "objected" and top and PURPOSE_ORDER[e.purpose] < top[0]:
            e = e.model_copy(update={"subsumed_by": top[1]})
        result.append(e)
    return result
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_responses.py -v`
Expected: 9 passed

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/responses.py core/tests/test_responses.py
git commit -m "feat(core): 版をまたぐ反応の畳み込みを追加

祖先への反応を含めないと、v1の異議を修正して合意を得ても異議が
永久に残り収束条件を一生満たせない。一方で無条件に継承すると
古い合意で誤って通るため、失効はセクション単位で判定する。"
```

---

## Task 15: check registryと有効なcheckの決定

**Files:**
- Create: `core/src/medo_core/checks.py`
- Create: `core/tests/test_checks.py`

**Interfaces:**
- Consumes: Task 4 の `ChangeManifest`、Task 8 の `Artifact`、Task 11 の `CheckRecorded`
- Produces: `CHECK_REGISTRY: dict[str, CheckSpec]` / `CheckSpec(binding, target_type, invalidating_sections, phase, confirmer)` / `checks_for_phase(phase) -> list[str]` / `effective_checks(events, ..., ) -> dict[str, CheckState]` / `CheckState(state, event_id, disposition)` / `detect_inconsistency(states, doc) -> list[str]` / `detect_ritualized(events, manifests) -> list[str]`

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_checks.py`:

```python
from medo_core.checks import (
    CHECK_REGISTRY,
    checks_for_phase,
    detect_inconsistency,
    detect_ritualized,
    effective_checks,
)
from medo_core.events import ArtifactTarget, CheckRecorded, RequirementsTarget
from medo_core.manifest import ChangeManifest, SectionChange
from medo_core.nodes import AsIs, Gap, Stakeholder
from medo_core.requirements import RequirementsDoc


def _recorded(ev_id, check, result, *, round_id=1, requirements_version=1,
              target=None, note="", disposition="open", finding_refs=()):
    ev = CheckRecorded(
        target=target or RequirementsTarget(version=requirements_version),
        occurred_on="2026-08-30", requirements_version=requirements_version,
        round_id=round_id, check=check, result=result, note=note,
        disposition=disposition, finding_refs=list(finding_refs),
    )
    return ev.model_copy(update={"id": ev_id})


def _manifest(version, *sections):
    return ChangeManifest(version=version,
                          changes=[SectionChange(section=s) for s in sections],
                          recorded_on="2026-08-30")


def test_discovery_phase_hides_convergence_checks():
    """初日から全項目を並べると「全部埋めないと動かない」圧を与える。"""
    discovery = set(checks_for_phase("discovery"))

    assert "reality_gap" in discovery
    assert "feasibility" not in discovery


def test_convergence_phase_includes_all_checks():
    assert set(checks_for_phase("convergence")) == set(CHECK_REGISTRY)


def test_unrecorded_check_is_unverified():
    states = effective_checks([], phase="discovery", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert states["reality_gap"].state == "unverified"


def test_persistent_check_survives_requirements_change():
    events = [_recorded("ev-1", "reality_gap", "completed")]

    states = effective_checks(events, phase="discovery", latest_requirements_version=3,
                              manifests=[_manifest(2, "as_is"), _manifest(3, "to_be")],
                              current_artifact_ids={})

    assert states["reality_gap"].state == "completed"


def test_version_bound_check_expires_on_relevant_section_change():
    events = [_recorded("ev-1", "feasibility", "completed")]

    states = effective_checks(events, phase="convergence", latest_requirements_version=2,
                              manifests=[_manifest(2, "constraints")],
                              current_artifact_ids={})

    assert states["feasibility"].state == "unverified"


def test_version_bound_check_survives_unrelated_change():
    events = [_recorded("ev-1", "feasibility", "completed")]

    states = effective_checks(events, phase="convergence", latest_requirements_version=2,
                              manifests=[_manifest(2, "stakeholders")],
                              current_artifact_ids={})

    assert states["feasibility"].state == "completed"


def test_decision_maker_check_expires_when_stakeholders_change():
    events = [_recorded("ev-1", "decision_maker", "completed")]

    states = effective_checks(events, phase="convergence", latest_requirements_version=2,
                              manifests=[_manifest(2, "stakeholders")],
                              current_artifact_ids={})

    assert states["decision_maker"].state == "unverified"


def test_artifact_bound_check_expires_when_target_is_regenerated():
    events = [_recorded("ev-1", "as_is_articulation", "completed",
                        target=ArtifactTarget(artifact_id="as-is-report-v1"))]

    states = effective_checks(events, phase="convergence", latest_requirements_version=1,
                              manifests=[],
                              current_artifact_ids={"as-is-report": "as-is-report-v2"})

    assert states["as_is_articulation"].state == "unverified"


def test_undeterminable_carries_disposition():
    events = [_recorded("ev-1", "to_be_articulation", "undeterminable",
                        note="方向性が未定", disposition="promoted")]

    states = effective_checks(events, phase="convergence", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert states["to_be_articulation"].state == "undeterminable"
    assert states["to_be_articulation"].disposition == "promoted"


def test_finding_without_corresponding_record_is_inconsistent():
    states = effective_checks([_recorded("ev-1", "past_attempts", "finding", note="あり")],
                              phase="discovery", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert "past_attempts" in detect_inconsistency(states, RequirementsDoc(project="p1"))


def test_completed_with_existing_record_is_inconsistent():
    doc = RequirementsDoc(project="p1",
                          stakeholders=[Stakeholder(id="sh-1", text="部長",
                                                    surfaced_by="inferred")])
    states = effective_checks([_recorded("ev-1", "hidden_stakeholders", "completed")],
                              phase="discovery", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert "hidden_stakeholders" in detect_inconsistency(states, doc)


def test_consistent_finding_is_not_reported():
    doc = RequirementsDoc(project="p1",
                          as_is=[AsIs(id="as-1", text="公表", visibility="public"),
                                 AsIs(id="as-2", text="実態", visibility="internal")],
                          gaps=[Gap(id="gap-1", text="乖離", kind="perception",
                                    from_as_is=["as-1", "as-2"])])
    states = effective_checks([_recorded("ev-1", "reality_gap", "finding",
                                         finding_refs=["gap-1"])],
                              phase="discovery", latest_requirements_version=1,
                              manifests=[], current_artifact_ids={})

    assert detect_inconsistency(states, doc) == []


def test_three_completed_rounds_with_substantive_changes_are_ritualized():
    events = [
        _recorded(f"ev-{n}", "hidden_stakeholders", "completed", round_id=n,
                  requirements_version=n)
        for n in (1, 2, 3)
    ]

    ritualized = detect_ritualized(events, [_manifest(n, "as_is") for n in (1, 2, 3)])

    assert "hidden_stakeholders" in ritualized


def test_completed_rounds_without_changes_are_not_ritualized():
    """ステークホルダーが限定されている案件では completed が続くのが正常。"""
    events = [
        _recorded(f"ev-{n}", "hidden_stakeholders", "completed", round_id=n,
                  requirements_version=n)
        for n in (1, 2, 3)
    ]

    assert detect_ritualized(events, manifests=[]) == []
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_checks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_core.checks'`

- [ ] **Step 3: 実装**

`core/src/medo_core/checks.py`:

```python
"""チェックリストの正本。

項目の定義と結果の記録はCLIが持ち、各ドキュメントにはその時点で関連する
項目を投影する。文書本文に埋め込むと更新が分散し、記録が本文に埋まって
CLIが未確認を検出できなくなる。
"""

from typing import Literal

from pydantic import BaseModel, Field

from medo_core.manifest import ChangeManifest, fold_substantive_sections

Binding = Literal["persistent", "version_bound", "artifact_bound"]

CORE_NODE_SECTIONS = ("as_is", "to_be", "gaps", "bottlenecks", "challenges", "constraints")


class CheckSpec(BaseModel):
    binding: Binding
    target_type: str | None = None          # artifact_bound のときの生成物type
    slide_kind: str | None = None
    invalidating_sections: tuple[str, ...] = ()
    phase: Literal["discovery", "convergence"] = "convergence"
    confirmer: Literal["consultant", "customer", "both"] = "consultant"


CHECK_REGISTRY: dict[str, CheckSpec] = {
    "source_quality": CheckSpec(binding="artifact_bound", target_type="research",
                                phase="discovery"),
    "reality_gap": CheckSpec(binding="persistent", phase="discovery", confirmer="both"),
    "past_attempts": CheckSpec(binding="persistent", phase="discovery", confirmer="both"),
    "hidden_stakeholders": CheckSpec(binding="persistent", phase="discovery",
                                     confirmer="both"),
    "as_is_articulation": CheckSpec(binding="artifact_bound", target_type="as-is-report",
                                    phase="discovery", confirmer="customer"),
    "decision_maker": CheckSpec(binding="persistent",
                                invalidating_sections=("stakeholders",), confirmer="both"),
    "internal_consistency": CheckSpec(binding="version_bound",
                                      invalidating_sections=CORE_NODE_SECTIONS),
    "expression_safety": CheckSpec(binding="artifact_bound", target_type="slides",
                                   slide_kind="discussion"),
    "to_be_articulation": CheckSpec(binding="version_bound",
                                    invalidating_sections=("to_be",), confirmer="customer"),
    "feasibility": CheckSpec(binding="version_bound",
                             invalidating_sections=("to_be", "constraints"),
                             confirmer="both"),
    "scope_agreement": CheckSpec(binding="version_bound",
                                 invalidating_sections=CORE_NODE_SECTIONS,
                                 confirmer="customer"),
}


class CheckState(BaseModel):
    state: Literal["unverified", "completed", "finding", "undeterminable"] = "unverified"
    event_id: str = ""
    disposition: Literal["open", "deferred", "promoted"] = "open"
    finding_refs: list[str] = Field(default_factory=list)


def checks_for_phase(phase: str) -> list[str]:
    if phase == "discovery":
        return [n for n, s in CHECK_REGISTRY.items() if s.phase == "discovery"]
    return list(CHECK_REGISTRY)


def effective_checks(
    events: list,
    *,
    phase: str,
    latest_requirements_version: int,
    manifests: list[ChangeManifest],
    current_artifact_ids: dict[str, str],
) -> dict[str, CheckState]:
    """現在の対象に適用される check それぞれの有効値を返す。"""
    states = {name: CheckState() for name in checks_for_phase(phase)}
    recorded = [e for e in events if e.kind == "check"]

    for event in sorted(recorded, key=lambda e: int(e.id.rsplit("-", 1)[1])):
        spec = CHECK_REGISTRY.get(event.check)
        if spec is None or event.check not in states:
            continue
        if _is_expired(event, spec, latest_requirements_version, manifests,
                       current_artifact_ids):
            continue
        states[event.check] = CheckState(
            state=event.result, event_id=event.id,
            disposition=event.disposition, finding_refs=event.finding_refs,
        )
    return states


def _is_expired(event, spec, latest_version, manifests, current_artifact_ids) -> bool:
    if spec.binding == "artifact_bound":
        current = current_artifact_ids.get(spec.target_type)
        return current is not None and (
            event.target.kind != "artifact" or event.target.artifact_id != current
        )
    if not spec.invalidating_sections:
        return False
    changed = fold_substantive_sections(manifests, from_version=event.requirements_version)
    return bool(set(spec.invalidating_sections) & changed)
```

対応レコードの整合検証と形骸化検出:

```python
def _finding_record_count(check: str, doc) -> int | None:
    """finding に対応するレコード件数。定義できない check は None を返す。"""
    if check == "reality_gap":
        return len([g for g in doc.gaps if g.kind == "perception"])
    if check == "past_attempts":
        return len(doc.attempts)
    if check == "hidden_stakeholders":
        return len([s for s in doc.stakeholders if s.surfaced_by == "inferred"])
    if check == "decision_maker":
        return len([s for s in doc.stakeholders if s.is_decision_maker])
    return None


def detect_inconsistency(states: dict[str, CheckState], doc) -> list[str]:
    """finding なのに対応レコードが0件、completed なのに存在する場合を報告する。

    報告であって強制ではない(readiness は通す)。
    """
    inconsistent = []
    for check, state in states.items():
        count = _finding_record_count(check, doc)
        if count is None:
            continue
        if state.state == "finding" and count == 0:
            inconsistent.append(check)
        elif state.state == "completed" and count > 0:
            inconsistent.append(check)
    return sorted(inconsistent)


def detect_ritualized(events: list, manifests: list[ChangeManifest]) -> list[str]:
    """要件に実質変更があったのに3周続けて completed の check を報告する。

    変更が無い周回を数に入れない。限定された案件では completed が続くのが正常。
    """
    changed_rounds = {
        m.version for m in manifests
        if not m.id_only_migration
        and any(c.change_kind == "substantive" for c in m.changes)
    }
    by_check: dict[str, list] = {}
    for e in events:
        if e.kind == "check" and e.requirements_version in changed_rounds:
            by_check.setdefault(e.check, []).append(e)

    ritualized = []
    for check, group in by_check.items():
        latest_per_round: dict[int, object] = {}
        for e in sorted(group, key=lambda e: int(e.id.rsplit("-", 1)[1])):
            latest_per_round[e.round_id] = e
        ordered = [latest_per_round[r] for r in sorted(latest_per_round)][-3:]
        if len(ordered) == 3 and all(e.result == "completed" for e in ordered):
            ritualized.append(check)
    return sorted(ritualized)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_checks.py -v`
Expected: 14 passed

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/checks.py core/tests/test_checks.py
git commit -m "feat(core): check registryと有効期間の判定を追加

「要件が更新されてもcheckを無効化しない」とすると、内容が変わっても
旧結果が通り続ける。項目ごとに持続・版束縛・artifact束縛を定義する。"
```

---

## Task 16: 進行記録CLIの追加

**Files:**
- Modify: `cli/src/medo_cli/main.py`
- Modify: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 12〜15
- Produces: `medo check add` / `medo review add` / `medo respond add` / `medo checkpoint answer`

- [ ] **Step 1: 失敗するテストを書く**

`cli/tests/test_cli.py` に追記:

```python
def test_check_add_records_result(runner):
    _save_minimal_requirements(runner, "p1")

    result = runner.invoke(app, [
        "check", "add", "--project", "p1", "--check", "reality_gap", "--result", "completed",
    ])

    assert result.exit_code == 0
    assert "recorded: ev-" in result.stdout


def test_check_add_rejects_undeterminable_without_note(runner):
    _save_minimal_requirements(runner, "p1")

    result = runner.invoke(app, [
        "check", "add", "--project", "p1", "--check", "to_be_articulation",
        "--result", "undeterminable",
    ])

    assert result.exit_code == 1
    assert "note" in result.stderr


def test_check_add_accepts_disposition(runner):
    _save_minimal_requirements(runner, "p1")

    result = runner.invoke(app, [
        "check", "add", "--project", "p1", "--check", "to_be_articulation",
        "--result", "undeterminable", "--note", "方向性が未定",
        "--disposition", "promoted",
    ])

    assert result.exit_code == 0


def test_respond_add_rejects_unknown_stakeholder(runner):
    _save_minimal_requirements(runner, "p1")

    result = runner.invoke(app, [
        "respond", "add", "--project", "p1", "--stakeholder", "sh-99",
        "--purpose", "to_be_go_ahead", "--reaction", "agreed",
    ])

    assert result.exit_code == 1
    assert "sh-99" in result.stderr


def test_checkpoint_answer_requires_existing_milestone(runner):
    _save_minimal_requirements(runner, "p1")

    result = runner.invoke(app, [
        "checkpoint", "answer", "--project", "p1", "--responds-to", "ev-99",
        "--answer", "generate",
    ])

    assert result.exit_code == 1
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest cli/tests/test_cli.py -k "check_add or respond_add or checkpoint" -v`
Expected: FAIL — `No such command 'check'`

- [ ] **Step 3: CLIコマンドを実装**

`cli/src/medo_cli/main.py` に追加:

```python
check_app = typer.Typer(help="発見プロセスの確認結果を記録する")
review_app = typer.Typer(help="AsIsレポートと討議用スライドのレビューを記録する")
respond_app = typer.Typer(help="ステークホルダーの反応を記録する")
checkpoint_app = typer.Typer(help="ToBeチェックポイントに回答する")
app.add_typer(check_app, name="check")
app.add_typer(review_app, name="review")
app.add_typer(respond_app, name="respond")
app.add_typer(checkpoint_app, name="checkpoint")


def _recorder() -> WorkflowRecorder:
    return WorkflowRecorder(get_storage())


def _latest_version(project: str) -> int:
    return RequirementsStore(get_storage()).latest_version(project)


@check_app.command("add")
def check_add(
    project: str = typer.Option(..., "--project"),
    check: str = typer.Option(..., "--check"),
    result: str = typer.Option(..., "--result", help="completed|finding|undeterminable"),
    note: str = typer.Option("", "--note"),
    refs: str = typer.Option("", "--refs", help="finding の該当ノードID(カンマ区切り)"),
    disposition: str = typer.Option("open", "--disposition",
                                    help="undeterminable の扱い: open|deferred|promoted"),
    artifact: str | None = typer.Option(None, "--artifact",
                                        help="artifact束縛の check の対象ID"),
) -> None:
    """チェック項目の確認結果を記録する。"""
    version = _latest_version(project)
    target = (
        ArtifactTarget(artifact_id=artifact) if artifact
        else RequirementsTarget(version=version)
    )
    event = CheckRecorded(
        target=target, occurred_on=date.today().isoformat(),
        requirements_version=version, round_id=0,
        check=check, result=result, note=note,
        finding_refs=[r.strip() for r in refs.split(",") if r.strip()],
        disposition=disposition,
    )
    typer.echo(f"recorded: {_recorder().record(project, event)}")
```

**`disposition` は同じ項目を record し直して更新する**。イベントは追記のみで、`effective_checks` が最新の有効値を採るため、後から扱いを決めたときは `medo check add --check <name> --result undeterminable --note <理由> --disposition promoted` を再度実行すればよい。更新用の別コマンドは設けない(進行の履歴を残すため)。この運用をCLIヘルプの `--disposition` 説明にも書く。

同様に `review add` / `respond add` / `checkpoint answer` を実装する:

```python
@review_app.command("add")
def review_add(
    project: str = typer.Option(..., "--project"),
    report: str = typer.Option(..., "--report", help="レビュー対象の as-is-report ID"),
    slides: str = typer.Option(..., "--slides", help="同時にレビューした討議用スライドID"),
    outcome: str = typer.Option(..., "--outcome", help="approved|changes_requested"),
    refs: str = typer.Option("", "--refs", help="要件側の所見ノードID(カンマ区切り)"),
    slide_findings: list[str] = typer.Option([], "--slide-finding",
                                             help="スライド固有の所見(複数可)"),
    reviewed_by: str = typer.Option("human", "--reviewed-by"),
) -> None:
    """AsIsレポートと討議用スライドのレビュー結果を記録する。"""
    event = AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report),
        occurred_on=date.today().isoformat(),
        requirements_version=_latest_version(project), round_id=0,
        outcome=outcome, reviewed_slides_id=slides,
        finding_refs=[r.strip() for r in refs.split(",") if r.strip()],
        slide_findings=list(slide_findings), reviewed_by=reviewed_by,
    )
    typer.echo(f"recorded: {_recorder().record(project, event)}")


@respond_app.command("add")
def respond_add(
    project: str = typer.Option(..., "--project"),
    stakeholder: str = typer.Option(..., "--stakeholder"),
    purpose: str = typer.Option(..., "--purpose",
                                help="as_is_alignment|to_be_go_ahead|phase_signoff"),
    reaction: str = typer.Option(..., "--reaction",
                                 help="empathized|acknowledged|agreed|objected|unclear"),
    artifact: str | None = typer.Option(None, "--artifact", help="生成物宛ての場合の対象ID"),
    note: str = typer.Option("", "--note"),
) -> None:
    """本人が対話で得た他者の反応を記録する(本人性の検証はしない)。"""
    version = _latest_version(project)
    target = (
        ArtifactTarget(artifact_id=artifact) if artifact
        else RequirementsTarget(version=version)
    )
    event = StakeholderResponded(
        target=target, occurred_on=date.today().isoformat(),
        requirements_version=version, round_id=0,
        stakeholder_id=stakeholder, purpose=purpose, reaction=reaction, note=note,
    )
    typer.echo(f"recorded: {_recorder().record(project, event)}")


@checkpoint_app.command("answer")
def checkpoint_answer(
    project: str = typer.Option(..., "--project"),
    responds_to: str = typer.Option(..., "--responds-to", help="回答対象の節目イベントID"),
    answer: str = typer.Option(..., "--answer", help="generate|defer"),
    focus: str = typer.Option("", "--focus", help="この周回で検証する仮説ID"),
) -> None:
    """ToBeを出す/更新するかの判断を記録する。"""
    version = _latest_version(project)
    event = ToBeCheckpointRecorded(
        target=RequirementsTarget(version=version),
        occurred_on=date.today().isoformat(),
        requirements_version=version, round_id=0,
        answer=answer, responds_to=responds_to,
    )
    event_id = _recorder().record(project, event)
    if focus:
        _recorder().set_focus(project, responds_to, focus)
    typer.echo(f"recorded: {event_id}")
```

`WorkflowRecorder.set_focus(project_id, milestone_id, hypothesis_id)` を追加する — 対象の `MilestoneDetected` の `focus_hypothesis_id` を更新し、参照先が実在する仮説であることを検証する。

- [ ] **Step 4: 要件保存を節目検出経路へ切り替える**

`medo requirements save`(Task 7)を `RequirementsStore.save` から `WorkflowRecorder.save_requirements` に差し替える。**これをしないと実利用で `MilestoneDetected` が一切作られず、`actions` の先頭が永久に `answer_tobe_checkpoint` にならない**。

```python
    version = WorkflowRecorder(get_storage()).save_requirements(
        project, doc, editorial_sections=tuple(editorial)
    )
```

テストを追加する:

```python
def test_requirements_save_records_milestone_through_cli(tmp_path, runner):
    """実利用の経路で節目が記録されないと、actionsが機能しない。"""
    doc = {"project": "p1", "as_is": [{"text": "実態", "visibility": "internal"}]}
    f = tmp_path / "req.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    runner.invoke(app, ["requirements", "save", "--project", "p1", "--file", str(f)])

    result = runner.invoke(app, ["status", "--project", "p1", "--format", "json"])

    assert "answer_tobe_checkpoint" in result.stdout
```

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run pytest cli/tests/ -v`
Expected: 全て pass

- [ ] **Step 6: リントとコミット**

```bash
uv run ruff check .
git add cli/src/medo_cli/main.py core/src/medo_core/workflow.py cli/tests/test_cli.py
git commit -m "feat(cli): 進行記録の4コマンドを追加

Skillは状態をホスト側に持たず、すべてCLI経由で受け渡す。
ステージごとに違うホストで実行しても続行できるようにするため。"
```

---

## Task 17: model診断(構造・リンク・カバレッジ)

**Files:**
- Create: `core/src/medo_core/diagnostics.py`
- Create: `core/tests/test_diagnostics.py`

**Interfaces:**
- Consumes: Task 2〜3 のノード型、Task 5 の `RequirementsDoc`
- Produces: `diagnostic_phase(doc) -> str` / `in_scope(nodes, include_scope) -> list` / `model_diagnostics(doc, artifacts, freshness, include_scope) -> dict`

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_diagnostics.py`:

```python
from medo_core.diagnostics import diagnostic_phase, model_diagnostics
from medo_core.nodes import (
    AsIs, Attempt, Bottleneck, Challenge, Gap, Hypothesis, Kpi, PromotionSource,
    Stakeholder, ToBe,
)
from medo_core.requirements import RequirementsDoc


def _doc(**kw) -> RequirementsDoc:
    return RequirementsDoc(project="p1", **kw)


def _model(doc, include_scope=("core",)) -> dict:
    return model_diagnostics(doc, artifacts={}, freshness={}, include_scope=include_scope)


def test_phase_is_discovery_until_first_to_be():
    """探索の初期に収束警告を出すと「全部埋めないと動かない」印象を与える。"""
    assert diagnostic_phase(_doc()) == "discovery"


def test_phase_becomes_convergence_when_to_be_exists():
    assert diagnostic_phase(_doc(to_be=[ToBe(id="tb-1", text="自動化")])) == "convergence"


def test_structure_counts_as_is_by_visibility():
    doc = _doc(as_is=[
        AsIs(id="as-1", text="公表", visibility="public"),
        AsIs(id="as-2", text="実態", visibility="internal", confidence="confirmed"),
    ])

    structure = _model(doc)["structure"]["as_is"]
    assert structure == {"count": 2, "confirmed": 1, "public": 1, "internal": 1}


def test_structure_excludes_out_of_scope_nodes_by_default():
    doc = _doc(challenges=[
        Challenge(id="ch-1", text="今回の課題"),
        Challenge(id="ch-2", text="今回は扱わない", scope="secondary"),
    ])

    assert _model(doc)["structure"]["challenges"]["count"] == 1


def test_include_scope_widens_the_diagnostic_range():
    doc = _doc(challenges=[
        Challenge(id="ch-1", text="今回の課題"),
        Challenge(id="ch-2", text="今回は扱わない", scope="secondary"),
    ])

    widened = _model(doc, include_scope=("core", "secondary"))
    assert widened["structure"]["challenges"]["count"] == 2


def test_scope_filter_does_not_apply_to_kpis():
    """scope を持たない型は常に全件が対象。"""
    doc = _doc(kpis=[Kpi(id="kpi-1", text="リードタイム", name="lead_time")])

    assert _model(doc)["structure"]["kpis"]["count"] == 1


def test_links_report_challenge_without_any_cause():
    doc = _doc(challenges=[Challenge(id="ch-1", text="後戻りが起きる")])

    assert _model(doc)["links"]["challenges_without_cause"] == ["ch-1"]


def test_links_exclude_promoted_challenge_from_cause_check():
    """昇格した課題は矛盾や判断不能が起点なので、真因リンクが空でも正常。"""
    doc = _doc(challenges=[Challenge(
        id="ch-1", text="どちらを前提にするか",
        promoted_from=PromotionSource(kind="internal_conflict", ref="gap-1"),
    )])

    assert _model(doc)["links"]["challenges_without_cause"] == []


def test_links_report_goal_gap_without_bottleneck():
    doc = _doc(gaps=[Gap(id="gap-1", text="乖離", kind="goal"),
                     Gap(id="gap-2", text="認識差", kind="perception")])

    assert _model(doc)["links"]["gaps_without_bottleneck"] == ["gap-1"]


def test_links_report_to_be_not_referenced_by_any_kpi():
    doc = _doc(to_be=[ToBe(id="tb-1", text="自動化"), ToBe(id="tb-2", text="即時化")],
               kpis=[Kpi(id="kpi-1", text="LT", name="lt", to_be_ids=["tb-1"])])

    assert _model(doc)["links"]["to_be_without_kpi"] == ["tb-2"]


def test_links_report_unvalidated_hypotheses():
    doc = _doc(hypotheses=[
        Hypothesis(id="hyp-1", kind="cause", statement="a"),
        Hypothesis(id="hyp-2", kind="cause", statement="b", status="validated"),
    ])

    assert _model(doc)["links"]["hypotheses_unvalidated"] == ["hyp-1"]


def test_coverage_reports_public_as_is_never_checked_against_reality():
    doc = _doc(as_is=[AsIs(id="as-1", text="公表", visibility="public")])

    assert _model(doc)["coverage"]["public_as_is_without_verification"] == ["as-1"]


def test_coverage_excludes_public_as_is_marked_reality_checked():
    """突合したが乖離が無かった場合、Gapは作られないため永久に未突合と誤検出される。"""
    doc = _doc(as_is=[AsIs(id="as-1", text="公表", visibility="public", reality_checked=True)])

    assert _model(doc)["coverage"]["public_as_is_without_verification"] == []


def test_coverage_excludes_public_as_is_referenced_by_perception_gap():
    doc = _doc(
        as_is=[AsIs(id="as-1", text="公表", visibility="public"),
               AsIs(id="as-2", text="実態", visibility="internal")],
        gaps=[Gap(id="gap-1", text="乖離", kind="perception", from_as_is=["as-1", "as-2"])],
    )

    assert _model(doc)["coverage"]["public_as_is_without_verification"] == []


def test_coverage_excludes_challenge_confirmed_as_not_attempted():
    """「取り組んでいない」という確認済みの事実は、未確認の空欄とは違う。"""
    doc = _doc(
        challenges=[Challenge(id="ch-1", text="後戻り")],
        attempts=[Attempt(id="at-1", description="未着手", outcome="not_attempted",
                          challenge_ids=["ch-1"])],
    )

    assert _model(doc)["coverage"]["challenges_without_attempt"] == []


def test_bottleneck_count_reflects_confirmed_only():
    doc = _doc(bottlenecks=[Bottleneck(id="bn-1", text="承認3階層", confidence="confirmed")])

    assert _model(doc)["structure"]["bottlenecks"] == {"count": 1, "confirmed": 1}


def test_stakeholder_structure_is_counted_without_scope():
    doc = _doc(stakeholders=[Stakeholder(id="sh-1", text="部長", confidence="confirmed")])

    assert _model(doc)["structure"]["stakeholders"] == {"count": 1, "confirmed": 1}
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_diagnostics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_core.diagnostics'`

- [ ] **Step 3: 実装**

`core/src/medo_core/diagnostics.py`:

```python
"""案件内容の充足診断。

診断は報告であって強制ではない。未接続を検出しても保存は拒否しない。
"""

from medo_core.requirements import RequirementsDoc

SCOPED_SECTIONS = (
    "as_is", "to_be", "gaps", "bottlenecks", "challenges", "constraints", "open_questions"
)


def diagnostic_phase(doc: RequirementsDoc) -> str:
    return "convergence" if doc.to_be else "discovery"


def in_scope(nodes: list, include_scope: tuple[str, ...]) -> list:
    """scope を持つノードだけを絞り込む。持たない型は全件返す。"""
    return [n for n in nodes if getattr(n, "scope", None) in include_scope or
            not hasattr(n, "scope")]


def model_diagnostics(
    doc: RequirementsDoc,
    artifacts: dict,
    freshness: dict,
    include_scope: tuple[str, ...] = ("core",),
) -> dict:
    scoped = {
        section: in_scope(getattr(doc, section), include_scope)
        for section in SCOPED_SECTIONS
    }
    return {
        "structure": _structure(doc, scoped),
        "links": _links(doc, scoped),
        "coverage": _coverage(doc, scoped, artifacts, freshness),
    }
```

構造の集計:

```python
def _confirmed(nodes: list) -> int:
    return len([n for n in nodes if n.confidence == "confirmed"])


def _structure(doc: RequirementsDoc, scoped: dict) -> dict:
    as_is = scoped["as_is"]
    to_be = scoped["to_be"]
    gaps = scoped["gaps"]
    return {
        "as_is": {
            "count": len(as_is), "confirmed": _confirmed(as_is),
            "public": len([n for n in as_is if n.visibility == "public"]),
            "internal": len([n for n in as_is if n.visibility == "internal"]),
        },
        "to_be": {
            "count": len(to_be), "confirmed": _confirmed(to_be),
            "assumed": len([n for n in to_be if n.confidence == "assumed"]),
            "open": len([n for n in to_be if n.confidence == "open"]),
        },
        "kpis": {"count": len(doc.kpis), "confirmed": _confirmed(doc.kpis)},
        "stakeholders": {
            "count": len(doc.stakeholders), "confirmed": _confirmed(doc.stakeholders),
        },
        "gaps": {
            "count": len(gaps),
            "perception": len([g for g in gaps if g.kind == "perception"]),
            "internal_conflict": len([g for g in gaps if g.kind == "internal_conflict"]),
            "goal": len([g for g in gaps if g.kind == "goal"]),
        },
        "bottlenecks": {
            "count": len(scoped["bottlenecks"]), "confirmed": _confirmed(scoped["bottlenecks"]),
        },
        "constraints": {
            "count": len(scoped["constraints"]), "confirmed": _confirmed(scoped["constraints"]),
        },
        "attempts": {"count": len(doc.attempts), "confirmed": _confirmed(doc.attempts)},
        "challenges": {
            "count": len(scoped["challenges"]), "confirmed": _confirmed(scoped["challenges"]),
        },
    }
```

リンクとカバレッジ:

```python
def _links(doc: RequirementsDoc, scoped: dict) -> dict:
    referenced_gap_ids = {g for b in doc.bottlenecks for g in b.gap_ids}
    referenced_to_be_ids = {t for k in doc.kpis for t in k.to_be_ids}
    return {
        "challenges_without_cause": sorted(
            c.id for c in scoped["challenges"]
            if not c.bottleneck_ids and not c.cause_hypothesis_ids and not c.promoted_from
        ),
        "gaps_without_bottleneck": sorted(
            g.id for g in scoped["gaps"]
            if g.kind == "goal" and g.id not in referenced_gap_ids
        ),
        "to_be_without_kpi": sorted(
            t.id for t in scoped["to_be"] if t.id not in referenced_to_be_ids
        ),
        "hypotheses_unvalidated": sorted(
            h.id for h in doc.hypotheses if h.status in ("unvalidated", "validating")
        ),
    }


def _coverage(doc: RequirementsDoc, scoped: dict, artifacts: dict, freshness: dict) -> dict:
    gap_checked_ids = {
        a for g in doc.gaps if g.kind == "perception" for a in g.from_as_is
    }
    attempted_challenge_ids = {c for a in doc.attempts for c in a.challenge_ids}
    return {
        "public_as_is_without_verification": sorted(
            n.id for n in scoped["as_is"]
            if n.visibility == "public" and not n.reality_checked
            and n.id not in gap_checked_ids
        ),
        "challenges_without_attempt": sorted(
            c.id for c in scoped["challenges"] if c.id not in attempted_challenge_ids
        ),
        "artifacts_without_challenge_coverage": sorted(
            a_id for a_id, f in freshness.items() if f.uncovered_challenge_ids
        ),
    }
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_diagnostics.py -v`
Expected: 17 passed

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/diagnostics.py core/tests/test_diagnostics.py
git commit -m "feat(core): 案件内容の構造・リンク・カバレッジ診断を追加

スコープを絞らないと、往復のたびに蓄積する課題とGAPすべてに
一律アラートが出て実務が埋没する。既定は scope:core のみを診る。"
```

---

## Task 18: readiness と round_delta

**Files:**
- Modify: `core/src/medo_core/diagnostics.py`
- Modify: `core/tests/test_diagnostics.py`

**Interfaces:**
- Consumes: Task 14 の `fold_responses` / `ConvergenceTarget`、Task 15 の `effective_checks`
- Produces: `readiness(doc, target, checks, responses, review_findings, include_scope) -> dict` / `phase_readiness(readiness_state, artifacts, freshness, responses) -> dict` / `round_delta(previous, saved, events, round_id) -> dict` / `to_be_is_grounded(doc, to_be_id) -> bool`

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_diagnostics.py` に追記:

```python
from medo_core.checks import CheckState
from medo_core.diagnostics import phase_readiness, readiness, round_delta
from medo_core.responses import ConvergenceTarget, EffectiveResponse


def _target(version=1, report="as-is-report-v1") -> ConvergenceTarget:
    return ConvergenceTarget(requirements_version=version, as_is_report_id=report)


def _all_checks(state="completed") -> dict:
    from medo_core.checks import CHECK_REGISTRY
    return {name: CheckState(state=state, event_id="ev-1") for name in CHECK_REGISTRY}


def _grounded_doc() -> RequirementsDoc:
    return _doc(
        as_is=[AsIs(id="as-1", text="実態", visibility="internal", confidence="confirmed")],
        to_be=[ToBe(id="tb-1", text="自動化", confidence="confirmed")],
        gaps=[Gap(id="gap-1", text="乖離", kind="goal",
                  from_as_is=["as-1"], from_to_be=["tb-1"])],
        stakeholders=[Stakeholder(id="sh-1", text="部長", is_decision_maker=True)],
    )


def _go_ahead() -> list[EffectiveResponse]:
    return [EffectiveResponse(stakeholder_id="sh-1", purpose="to_be_go_ahead",
                              reaction="agreed", event_id="ev-9")]


def _codes(result: dict) -> list[str]:
    return [c["code"] for c in result["failed_conditions"]]


def test_readiness_is_not_evaluable_in_discovery_phase():
    result = readiness(_doc(), _target(), _all_checks(), [], review_findings=[])

    assert result["state"] == "not_evaluable"


def test_readiness_reports_missing_internal_as_is():
    doc = _doc(to_be=[ToBe(id="tb-1", text="自動化")])

    assert "internal_as_is_missing" in _codes(
        readiness(doc, _target(), _all_checks(), [], review_findings=[])
    )


def test_readiness_reports_confirmed_to_be_without_grounding():
    """公開情報だけのAsIsから確定したToBeは理想の正論に終わる。"""
    doc = _doc(
        as_is=[AsIs(id="as-1", text="実態", visibility="internal", confidence="confirmed")],
        to_be=[ToBe(id="tb-1", text="自動化", confidence="confirmed")],
    )

    assert "unsupported_confirmed_to_be" in _codes(
        readiness(doc, _target(), _all_checks(), [], review_findings=[])
    )


def test_readiness_accepts_to_be_grounded_through_goal_gap():
    result = readiness(_grounded_doc(), _target(), _all_checks(), _go_ahead(),
                       review_findings=[])

    assert "unsupported_confirmed_to_be" not in _codes(result)


def test_readiness_reports_unrecorded_checks():
    checks = _all_checks()
    checks["reality_gap"] = CheckState()

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert {"code": "check_missing", "refs": ["reality_gap"]} in result["failed_conditions"]


def test_undeterminable_with_open_disposition_blocks_convergence():
    """すべてを undeterminable と記録すれば収束できる抜け道を塞ぐ。"""
    checks = _all_checks()
    checks["to_be_articulation"] = CheckState(state="undeterminable", disposition="open")

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert {"code": "undeterminable_open", "refs": ["to_be_articulation"]} in \
        result["failed_conditions"]


def test_undeterminable_with_disposition_decided_does_not_block():
    checks = _all_checks()
    checks["to_be_articulation"] = CheckState(state="undeterminable", disposition="deferred")

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert result["state"] == "ready"


def test_reality_gap_cannot_be_deferred_only_promoted():
    """判断できないまま先へ進むと提案の土台が崩れる2項目は保留を許さない。"""
    checks = _all_checks()
    checks["reality_gap"] = CheckState(state="undeterminable", disposition="deferred")

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert "undeterminable_open" in _codes(result)


def test_reality_gap_promoted_unblocks_convergence():
    checks = _all_checks()
    checks["reality_gap"] = CheckState(state="undeterminable", disposition="promoted")

    result = readiness(_grounded_doc(), _target(), checks, _go_ahead(), review_findings=[])

    assert result["state"] == "ready"


def test_readiness_reports_missing_report_for_current_version():
    result = readiness(_grounded_doc(), ConvergenceTarget(requirements_version=1),
                       _all_checks(), _go_ahead(), review_findings=[])

    assert "as_is_report_missing" in _codes(result)


def test_readiness_requires_go_ahead_not_phase_signoff():
    """この段階では打ち手も費用感も提示していない。フェーズ完了承認は求めない。"""
    result = readiness(_grounded_doc(), _target(), _all_checks(), [], review_findings=[])

    assert "to_be_go_ahead_missing" in _codes(result)
    assert "decision_maker_signoff_missing" not in _codes(result)


def test_readiness_reports_open_objection_of_high_influence_stakeholder():
    doc = _grounded_doc()
    doc.stakeholders.append(Stakeholder(id="sh-2", text="情シス部長", influence="high"))
    responses = _go_ahead() + [EffectiveResponse(
        stakeholder_id="sh-2", purpose="as_is_alignment", reaction="objected",
        event_id="ev-7")]

    result = readiness(doc, _target(), _all_checks(), responses, review_findings=[])

    assert {"code": "high_influence_objection_open", "refs": ["ev-7"]} in \
        result["failed_conditions"]


def test_subsumed_objection_does_not_block():
    doc = _grounded_doc()
    doc.stakeholders.append(Stakeholder(id="sh-2", text="情シス部長", influence="high"))
    responses = _go_ahead() + [EffectiveResponse(
        stakeholder_id="sh-2", purpose="as_is_alignment", reaction="objected",
        event_id="ev-7", subsumed_by="ev-8")]

    result = readiness(doc, _target(), _all_checks(), responses, review_findings=[])

    assert "high_influence_objection_open" not in _codes(result)


def test_phase_readiness_is_not_evaluable_without_prfaq():
    result = phase_readiness("ready", artifacts={}, freshness={}, responses=[],
                             target=_target())

    assert result["state"] == "not_evaluable"


def test_round_delta_counts_undeterminable_only_on_first_detection():
    """毎周「やはり判断できません」で progress_count が非ゼロになると
    進捗のない空転が発散警告に引っかからなくなる。"""
    from medo_core.events import CheckRecorded, RequirementsTarget

    def _ev(ev_id, round_id):
        ev = CheckRecorded(
            target=RequirementsTarget(version=1), occurred_on="2026-08-30",
            requirements_version=1, round_id=round_id,
            check="to_be_articulation", result="undeterminable", note="未定",
        )
        return ev.model_copy(update={"id": ev_id})

    events = [_ev("ev-1", 1), _ev("ev-2", 2)]

    assert round_delta(None, _doc(), events, round_id=1)["undeterminable_found"] == \
        ["to_be_articulation"]
    assert round_delta(None, _doc(), events, round_id=2)["undeterminable_found"] == []
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_diagnostics.py -k readiness -v`
Expected: FAIL — `ImportError: cannot import name 'readiness'`

- [ ] **Step 3: 実装**

`core/src/medo_core/diagnostics.py` に追記:

```python
from medo_core.artifacts import Freshness
from medo_core.checks import CheckState, checks_for_phase
from medo_core.responses import ConvergenceTarget

# 判断できないまま進むと提案の土台が崩れるため、保留を許さず昇格のみで先へ進める。
NO_DEFER_CHECKS = ("reality_gap", "decision_maker")


def to_be_is_grounded(doc: RequirementsDoc, to_be_id: str) -> bool:
    """ToBeと内部実態を結ぶ経路が goal gap を通じて存在するか。"""
    internal_ids = {
        a.id for a in doc.as_is if a.visibility == "internal" and a.confidence != "open"
    }
    return any(
        g.kind == "goal" and to_be_id in g.from_to_be
        and internal_ids & set(g.from_as_is)
        for g in doc.gaps
    )


def readiness(
    doc: RequirementsDoc,
    target: ConvergenceTarget,
    checks: dict[str, CheckState],
    responses: list,
    review_findings: list[str],
    include_scope: tuple[str, ...] = ("core",),
) -> dict:
    """標準周回の収束判定。保存ゲートではなく診断である。"""
    if diagnostic_phase(doc) == "discovery":
        return {"state": "not_evaluable", "failed_conditions": []}

    failed: list[dict] = []
    scoped_as_is = in_scope(doc.as_is, include_scope)
    scoped_to_be = in_scope(doc.to_be, include_scope)

    if not [a for a in scoped_as_is if a.visibility == "internal"]:
        failed.append({"code": "internal_as_is_missing", "refs": []})

    confirmed = [t for t in scoped_to_be if t.confidence == "confirmed"]
    ungrounded = [t.id for t in confirmed if not to_be_is_grounded(doc, t.id)]
    if not confirmed or ungrounded:
        failed.append({"code": "unsupported_confirmed_to_be", "refs": sorted(ungrounded)})

    if target.as_is_report_id is None:
        failed.append({"code": "as_is_report_missing", "refs": []})

    failed.extend(_check_conditions(doc, checks))

    if review_findings:
        failed.append({"code": "review_findings_open", "refs": sorted(review_findings)})

    failed.extend(_response_conditions(doc, responses))

    return {"state": "ready" if not failed else "not_ready", "failed_conditions": failed}
```

条件の内訳:

```python
def _check_conditions(doc: RequirementsDoc, checks: dict[str, CheckState]) -> list[dict]:
    expected = checks_for_phase(diagnostic_phase(doc))
    missing = sorted(
        name for name in expected
        if checks.get(name, CheckState()).state == "unverified"
    )
    blocking = sorted(
        name for name in expected
        if (s := checks.get(name, CheckState())).state == "undeterminable"
        and (s.disposition == "open"
             or (name in NO_DEFER_CHECKS and s.disposition != "promoted"))
    )
    conditions = []
    if missing:
        conditions.append({"code": "check_missing", "refs": missing})
    if blocking:
        conditions.append({"code": "undeterminable_open", "refs": blocking})
    return conditions


def _response_conditions(doc: RequirementsDoc, responses: list) -> list[dict]:
    conditions = []
    decision_makers = {s.id for s in doc.stakeholders if s.is_decision_maker}
    agreed = {
        r.stakeholder_id for r in responses
        if r.purpose == "to_be_go_ahead" and r.reaction == "agreed" and not r.expired
    }
    if not decision_makers or not (decision_makers & agreed):
        conditions.append({"code": "to_be_go_ahead_missing",
                           "refs": sorted(decision_makers)})

    high_influence = {s.id for s in doc.stakeholders if s.influence == "high"}
    open_objections = sorted(
        r.event_id for r in responses
        if r.reaction == "objected" and not r.subsumed_by
        and r.stakeholder_id in high_influence
    )
    if open_objections:
        conditions.append({"code": "high_influence_objection_open", "refs": open_objections})
    return conditions
```

`phase_readiness` と `round_delta`:

```python
def phase_readiness(
    readiness_state: str,
    artifacts: dict,
    freshness: dict,
    responses: list,
    target: ConvergenceTarget,
) -> dict:
    """フェーズ完了ゲート。最終提案スライドを提示した後に評価する。

    「何を見て承認したか」を一意に決めるため、現在の最終提案スライドへの
    signoff だけを有効とする(fold_responses が現在対象で畳み込む)。
    """
    prfaq = [a_id for a_id, a in artifacts.items() if a.type == "prfaq"]
    if not prfaq:
        return {"state": "not_evaluable", "failed_conditions": []}

    failed = []
    if readiness_state != "ready":
        failed.append({"code": "convergence_not_ready", "refs": []})
    if not any(freshness.get(a_id, None) and freshness[a_id].state != "stale" for a_id in prfaq):
        failed.append({"code": "prfaq_missing_or_stale", "refs": []})

    current_final = target.final_slides_id
    if current_final is None or freshness.get(current_final, Freshness()).state == "stale":
        failed.append({"code": "final_slides_missing_or_stale", "refs": []})
    elif not any(
        r.purpose == "phase_signoff" and r.reaction == "agreed" and not r.expired
        for r in responses
    ):
        failed.append({"code": "phase_signoff_missing", "refs": []})

    return {"state": "ready" if not failed else "not_ready", "failed_conditions": failed}


def round_delta(
    previous: RequirementsDoc | None,
    saved: RequirementsDoc,
    events: list,
    round_id: int,
    resolved_objections: int = 0,
) -> dict:
    """その周回で新たに得られたものを返す。回ること自体が価値であることを示す。

    resolved_objections は「有効値から外れた objected の件数」であり、畳み込みの
    前後を比較しないと決まらないため、呼び出し側(status)が算出して渡す。
    既存Challengeへ後付けした昇格も promoted_challenges に数える。
    """
    def added(section: str) -> list:
        old = {n.id for n in getattr(previous, section)} if previous else set()
        return [n for n in getattr(saved, section) if n.id not in old]

    old_confidence = (
        {n.id: n.confidence
         for section in SCOPED_SECTIONS for n in getattr(previous, section)}
        if previous else {}
    )
    raised = sorted(
        n.id
        for section in SCOPED_SECTIONS
        for n in getattr(saved, section)
        if n.id in old_confidence
        and _confidence_rank(n.confidence) > _confidence_rank(old_confidence[n.id])
    )

    old_promoted = (
        {c.id for c in previous.challenges if c.promoted_from} if previous else set()
    )
    newly_promoted = [
        c for c in saved.challenges if c.promoted_from and c.id not in old_promoted
    ]

    delta = {
        "new_internal_as_is": len([a for a in added("as_is") if a.visibility == "internal"]),
        "new_constraints": len(added("constraints")),
        "resolved_objections": resolved_objections,
        "promoted_challenges": len(newly_promoted),
        "confidence_raised": raised,
        "undeterminable_found": _first_undeterminable(events, round_id),
    }
    delta["progress_count"] = sum(
        len(v) if isinstance(v, list) else v for v in delta.values()
    )
    return delta


def _confidence_rank(value: str) -> int:
    return {"open": 0, "assumed": 1, "confirmed": 2}[value]


def _first_undeterminable(events: list, round_id: int) -> list[str]:
    """2周以上続けて同じ項目が判断不能のままなら数えない。初回の発見のみ前進。"""
    seen_before: set[str] = set()
    found: list[str] = []
    for e in sorted(events, key=lambda e: e.round_id):
        if e.kind != "check" or e.result != "undeterminable":
            continue
        if e.round_id == round_id and e.check not in seen_before:
            found.append(e.check)
        if e.round_id < round_id:
            seen_before.add(e.check)
    return sorted(set(found))
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/ -v`
Expected: 全て pass

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/diagnostics.py core/tests/test_diagnostics.py
git commit -m "feat(core): 収束判定と周回成果の算出を追加

標準周回の出口を to_be_go_ahead とする。この段階では打ち手も費用感も
提示しておらず、フェーズ完了承認を求めると永久に不合格になる。"
```

---

## Task 19: statusコンテキストの収集とworkflow枝

**Files:**
- Create: `core/src/medo_core/context.py`
- Create: `core/tests/test_context.py`

**Interfaces:**
- Consumes: Task 4・8〜18 のすべて
- Produces: `StatusContext`(下記の全フィールド)/ `collect(storage, project_id, *, include_scope, today) -> StatusContext` / `workflow_branch(ctx) -> dict`

**分割の理由**: `status.py` に収集・診断・action合成を全部置くと、1関数が3つの責務を持ち、テストが「何を検証しているか」を表せない。収集(このタスク)と提示(Task 20)を分ける。

`StatusContext` は診断に必要な素材をすべて解決済みで持つ。**後続が新たな判断を挟まないよう、曖昧さの残るものはここで確定させる**。

```python
class StatusContext(BaseModel):
    project_id: str
    doc: RequirementsDoc
    previous_doc: RequirementsDoc | None
    phase: str                             # discovery | convergence
    include_scope: tuple[str, ...]
    target: ConvergenceTarget
    artifacts: dict[str, Artifact]
    freshness: dict[str, Freshness]
    manifests: list[ChangeManifest]
    events: list
    checks: dict[str, CheckState]
    responses: list[EffectiveResponse]
    round_count: int
    pending_milestones: list[str]          # 未回答の MilestoneDetected のID
    focus_hypothesis: str
    open_review_findings: list[str]
    resolved_objections: int
```

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_context.py`:

```python
from datetime import date

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.context import collect, workflow_branch
from medo_core.events import ArtifactTarget, AsIsReportReviewed, StakeholderResponded
from medo_core.nodes import AsIs, Stakeholder, ToBe
from medo_core.requirements import RequirementsDoc
from medo_core.storage import LocalJsonStorage
from medo_core.workflow import WorkflowRecorder

TODAY = date(2026, 8, 30)


def _project(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    WorkflowRecorder(storage).save_requirements("p1", RequirementsDoc(
        project="p1",
        as_is=[AsIs(text="実態", visibility="internal")],
        stakeholders=[Stakeholder(text="部長", is_decision_maker=True)],
    ), today=TODAY)
    return storage


def _report(storage, requirements_version=1) -> str:
    return ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="as-is-report", requirements_version=requirements_version,
        generated_by="claude", content="# 現状",
    ))


def test_collect_resolves_current_target_from_latest_version(tmp_path):
    storage = _project(tmp_path)
    report_id = _report(storage)

    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    assert ctx.target.as_is_report_id == report_id


def test_collect_reports_unanswered_milestone(tmp_path):
    """未回答は「対応する回答を持たない MilestoneDetected」として一意に導く。"""
    storage = _project(tmp_path)

    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    assert len(ctx.pending_milestones) == 1


def test_collect_clears_pending_after_checkpoint_answer(tmp_path):
    from medo_core.events import RequirementsTarget, ToBeCheckpointRecorded

    storage = _project(tmp_path)
    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)
    WorkflowRecorder(storage).record("p1", ToBeCheckpointRecorded(
        target=RequirementsTarget(version=1), occurred_on="2026-08-30",
        requirements_version=1, round_id=0, answer="generate",
        responds_to=ctx.pending_milestones[0],
    ))

    assert collect(storage, "p1", include_scope=("core",), today=TODAY).pending_milestones == []


def test_open_review_finding_is_cleared_by_approval_of_successor(tmp_path):
    """収束条件は「レビューがある」ではなく「未解決の差し戻しが無い」。"""
    storage = _project(tmp_path)
    report_v1 = _report(storage)
    slides_v1 = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=1,
        derived_from=[report_v1], generated_by="claude", content="# 討議",
    ))
    rec = WorkflowRecorder(storage)
    rec.record("p1", AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report_v1), occurred_on="2026-08-30",
        requirements_version=1, round_id=0, outcome="changes_requested",
        reviewed_slides_id=slides_v1, slide_findings=["見出しが非難調"],
    ))
    assert collect(storage, "p1", include_scope=("core",),
                   today=TODAY).open_review_findings != []

    report_v2 = _report(storage)
    slides_v2 = ArtifactStore(storage).save("p1", Artifact(
        project="p1", type="slides", slide_kind="discussion", requirements_version=1,
        derived_from=[report_v2], generated_by="claude", content="# 討議2",
    ))
    rec.record("p1", AsIsReportReviewed(
        target=ArtifactTarget(artifact_id=report_v2), occurred_on="2026-08-31",
        requirements_version=1, round_id=0, outcome="approved",
        reviewed_slides_id=slides_v2,
    ))

    assert collect(storage, "p1", include_scope=("core",),
                   today=TODAY).open_review_findings == []


def test_resolved_objections_counts_objections_no_longer_effective(tmp_path):
    storage = _project(tmp_path)
    report_v1 = _report(storage)
    rec = WorkflowRecorder(storage)
    rec.record("p1", StakeholderResponded(
        target=ArtifactTarget(artifact_id=report_v1), occurred_on="2026-08-30",
        requirements_version=1, round_id=0,
        stakeholder_id="sh-1", purpose="as_is_alignment", reaction="objected",
    ))
    report_v2 = _report(storage)
    rec.record("p1", StakeholderResponded(
        target=ArtifactTarget(artifact_id=report_v2), occurred_on="2026-08-31",
        requirements_version=1, round_id=0,
        stakeholder_id="sh-1", purpose="as_is_alignment", reaction="agreed",
    ))

    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    assert ctx.resolved_objections == 1


def test_workflow_branch_reports_divergence_after_two_empty_rounds(tmp_path):
    """発散は停止条件ではなく、論点を絞る合図として報告する。"""
    storage = _project(tmp_path)
    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    branch = workflow_branch(ctx)

    assert branch["loop"]["divergence_warning"] is False


def test_workflow_branch_carries_checks_and_responses(tmp_path):
    storage = _project(tmp_path)
    ctx = collect(storage, "p1", include_scope=("core",), today=TODAY)

    branch = workflow_branch(ctx)

    assert set(branch) == {"checks", "review", "responses", "loop"}
    assert "states" in branch["checks"]
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_core.context'`

- [ ] **Step 3: `collect` を実装**

```python
"""診断の素材を1回の走査で解決する。

status.py が収集と提示を兼ねると、1関数が3つの責務を持ちテストが
「何を検証しているか」を表せなくなる。
"""


def collect(
    storage: Storage,
    project_id: str,
    *,
    include_scope: tuple[str, ...] = ("core",),
    today: date | None = None,
) -> StatusContext:
    reqs = RequirementsStore(storage)
    version = reqs.latest_version(project_id)
    doc = reqs.get(project_id)
    if doc is None:
        raise ValueError(f"プロジェクトが存在しません: {project_id}")

    artifacts = ArtifactStore(storage)._load_all(project_id)
    manifests = ManifestStore(storage).list(project_id)
    events = EventStore(storage).list(project_id)
    target = resolve_convergence_target(version, artifacts)

    core_challenge_ids = {
        c.id for c in doc.challenges if c.scope in include_scope
    }
    freshness = ArtifactStore(storage).freshness(
        project_id, version, core_challenge_ids,
        is_citation_stale=make_citation_checker(storage, project_id),
        today=today,
    )

    responses = fold_responses(events, target, artifacts, manifests)
    checks = effective_checks(
        events, phase=diagnostic_phase(doc), latest_requirements_version=version,
        manifests=manifests, current_artifact_ids=_current_artifact_ids(artifacts),
    )
    return StatusContext(
        project_id=project_id, doc=doc,
        previous_doc=reqs.get(project_id, version - 1) if version > 1 else None,
        phase=diagnostic_phase(doc), include_scope=include_scope,
        target=target, artifacts=artifacts, freshness=freshness,
        manifests=manifests, events=events, checks=checks, responses=responses,
        round_count=WorkflowRecorder(storage).round_count(project_id),
        pending_milestones=_pending_milestones(events),
        focus_hypothesis=_focus_hypothesis(events),
        open_review_findings=_open_review_findings(events, artifacts, doc),
        resolved_objections=_resolved_objections(events, responses),
    )
```

補助関数:

```python
def _current_artifact_ids(artifacts: dict) -> dict[str, str]:
    """型ごとの最新版ID。artifact束縛checkの失効判定に使う。"""
    latest: dict[str, str] = {}
    for a_id, a in artifacts.items():
        key = a.type
        if key not in latest or artifacts[latest[key]].version < a.version:
            latest[key] = a_id
    return latest


def _pending_milestones(events: list) -> list[str]:
    answered = {e.responds_to for e in events if e.kind == "tobe_checkpoint"}
    return [e.id for e in events if e.kind == "milestone" and e.id not in answered]


def _focus_hypothesis(events: list) -> str:
    for e in reversed(events):
        if e.kind == "milestone" and e.focus_hypothesis_id:
            return e.focus_hypothesis_id
    return ""


def _open_review_findings(events: list, artifacts: dict, doc) -> list[str]:
    """未解決の changes_requested を返す。

    解消は (1) 同系列の後継への approved (2) finding_refs が指すノードが
    すべて解消(削除または confirmed)されたとき。slide_findings は
    機械判定できないため (1) でのみ解消する。
    """
    reviews = [e for e in events if e.kind == "asis_review"]
    approved_versions = {
        artifacts[e.target.artifact_id].requirements_version
        for e in reviews
        if e.outcome == "approved" and e.target.artifact_id in artifacts
    }
    node_state = {
        n.id: n.confidence
        for section in ("gaps", "challenges", "open_questions")
        for n in getattr(doc, section)
    }
    open_refs: list[str] = []
    for e in reviews:
        if e.outcome != "changes_requested":
            continue
        version = artifacts.get(e.target.artifact_id)
        if version and any(v >= version.requirements_version for v in approved_versions):
            continue
        if e.slide_findings:
            open_refs.append(e.id)
        open_refs.extend(
            ref for ref in e.finding_refs
            if node_state.get(ref) not in (None, "confirmed")
        )
    return sorted(set(open_refs))


def _resolved_objections(events: list, responses: list) -> int:
    """記録された objected のうち、有効値から外れたものの件数。"""
    recorded = {e.id for e in events if e.kind == "response" and e.reaction == "objected"}
    still_effective = {
        r.event_id for r in responses if r.reaction == "objected" and not r.subsumed_by
    }
    return len(recorded - still_effective)
```

- [ ] **Step 4: `workflow_branch` を実装**

```python
def workflow_branch(ctx: StatusContext) -> dict:
    delta = round_delta(
        ctx.previous_doc, ctx.doc, ctx.events, ctx.round_count,
        resolved_objections=ctx.resolved_objections,
    )
    return {
        "checks": {
            "states": {name: s.state for name, s in ctx.checks.items()},
            "inconsistent": detect_inconsistency(ctx.checks, ctx.doc),
            "ritualized": detect_ritualized(ctx.events, ctx.manifests),
        },
        "review": {
            "current_target": ctx.target.as_is_report_id,
            "open_findings": ctx.open_review_findings,
        },
        "responses": {
            "effective": [
                {"stakeholder_id": r.stakeholder_id, "purpose": r.purpose,
                 "reaction": r.reaction}
                for r in ctx.responses if not r.subsumed_by and not r.expired
            ],
            "open_objections": sorted(
                r.event_id for r in ctx.responses
                if r.reaction == "objected" and not r.subsumed_by
            ),
            "go_ahead": _go_ahead_summary(ctx),
            "subsumed": sorted(r.event_id for r in ctx.responses if r.subsumed_by),
        },
        "loop": {
            "round_count": ctx.round_count,
            "focus_hypothesis": ctx.focus_hypothesis,
            "round_delta": delta,
            "checkpoint": {
                "state": "pending" if ctx.pending_milestones else "answered",
                "pending_ids": ctx.pending_milestones,
            },
            "divergence_warning": _is_diverging(ctx, delta),
        },
    }
```

`_is_diverging` は**直近2周の `progress_count` がいずれも0**のときTrue。各周回の `progress_count` は、その周回の要件版と `previous_doc` から `round_delta` を再計算して得る。周回が2未満のときはFalse。

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run pytest core/tests/test_context.py -v`
Expected: 7 passed

- [ ] **Step 6: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/context.py core/tests/test_context.py
git commit -m "feat(core): 診断素材の収集を分離

status が収集と提示を兼ねると、1関数が3つの責務を持ちテストが
何を検証しているか表せなくなる。曖昧さの残る解決(現在対象・未回答の
節目・未解決の差し戻し)を収集側で確定させ、提示側が判断を挟まないようにする。"
```

---

## Task 19b: statusの4階層とactions

**Files:**
- Modify: `core/src/medo_core/status.py`
- Modify: `core/tests/test_status.py`

**Interfaces:**
- Consumes: Task 19 の `collect` / `workflow_branch`、Task 17〜18 の診断
- Produces: `project_status(storage, project_id, knowledge_root=None, today=None, *, view="summary", include_scope=("core",)) -> dict` / `build_actions(ctx, model, readiness_result) -> list[dict]`

**既存シグネチャを壊さない**: 現行は `project_status(storage, project_id, knowledge_root, today=None)` で、`knowledge_root` は位置引数。**位置引数のまま残し、新規は全てキーワード専用にする**。要件が存在しないプロジェクトは、例外にせず現行どおり `next_step: "hearing"` を返す(CLIの既存挙動を壊さないため)。

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_status.py` に追記(既存テストは変更しない):

```python
def _codes(status: dict) -> list[str]:
    return [a["code"] for a in status["actions"]]


def test_status_returns_four_branches_in_full_view(tmp_path):
    storage = _project(tmp_path)

    status = project_status(storage, "p1", tmp_path, view="full")

    assert set(status) >= {"model", "workflow", "readiness", "actions", "diagnostic_phase"}


def test_summary_view_puts_actions_first(tmp_path):
    """Skillが最初に読むものを「足りない」ではなく「次にできること」にする。"""
    storage = _project(tmp_path)

    status = project_status(storage, "p1", tmp_path)

    assert list(status)[0] == "actions"


def test_summary_view_omits_failed_conditions(tmp_path):
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert "failed_conditions" not in status["readiness"]


def test_branch_view_returns_only_that_branch(tmp_path):
    status = project_status(_project(tmp_path), "p1", tmp_path, view="model")

    assert set(status) == {"project", "diagnostic_phase", "model"}


def test_missing_project_still_returns_phase1_shape(tmp_path):
    """既存CLIの挙動を壊さない。"""
    status = project_status(LocalJsonStorage(tmp_path), "unknown", tmp_path)

    assert status["next_step"] == "hearing"


def test_discovery_phase_still_returns_actions(tmp_path):
    """readiness を出さない段階でも、次に何をすべきかは示す。"""
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert "draft_strawman_to_be" in _codes(status)


def test_unanswered_milestone_is_the_top_action(tmp_path):
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert _codes(status)[0] == "answer_tobe_checkpoint"


def test_next_step_keeps_phase1_vocabulary(tmp_path):
    """フェーズ1のSkillは next_step を完全一致で分岐している。"""
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert status["next_step"] in {
        "hearing", "propose-options", "grow-prfaq",
        "regenerate-stale-artifacts", "up-to-date",
    }


def test_summary_view_keeps_phase1_compatibility_fields(tmp_path):
    status = project_status(_project(tmp_path), "p1", tmp_path)

    assert set(status) >= {"requirements", "facts", "artifacts", "next_step"}


def test_run_check_is_not_offered_without_its_target(tmp_path):
    """討議用スライドが無い状態で expression_safety を求めても実行できない。"""
    codes_with_refs = [
        a for a in project_status(_project(tmp_path), "p1", tmp_path)["actions"]
        if a["code"] == "run_check"
    ]

    assert all("expression_safety" not in a.get("refs", []) for a in codes_with_refs)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_status.py -v`
Expected: FAIL — `TypeError: project_status() got an unexpected keyword argument 'view'`

- [ ] **Step 3: `project_status` を再構成**

```python
def project_status(
    storage: Storage,
    project_id: str,
    knowledge_root: Path | None = None,
    today: date | None = None,
    *,
    view: str = "summary",
    include_scope: tuple[str, ...] = ("core",),
) -> dict:
    """現在地と次にできることを返す。診断は報告であって強制ではない。"""
    if RequirementsStore(storage).latest_version(project_id) == 0:
        return _empty_status(project_id)

    ctx = collect(storage, project_id, include_scope=include_scope, today=today)
    model = model_diagnostics(ctx.doc, ctx.artifacts, ctx.freshness, include_scope)
    workflow = workflow_branch(ctx)
    ready = readiness(ctx.doc, ctx.target, ctx.checks, ctx.responses,
                      ctx.open_review_findings, include_scope)
    actions = build_actions(ctx, model, ready)

    branches = {"model": model, "workflow": workflow,
                "readiness": ready, "actions": actions}
    head = {"project": project_id, "diagnostic_phase": ctx.phase}
    if view in branches:
        return {**head, view: branches[view]}
    compat = _phase1_fields(storage, ctx, knowledge_root, today)
    if view == "full":
        return {**head, **branches,
                "phase_readiness": phase_readiness(
                    ready["state"], ctx.artifacts, ctx.freshness,
                    ctx.responses, ctx.target),
                **compat}
    return _summary(project_id, ctx, workflow, ready, actions, compat)
```

`_phase1_fields` は**既存の `project_status` 本体をそのまま関数として切り出す**(`requirements` / `facts` / `artifacts` / `next_step`)。**`next_step` のロジックは一切変更しない**。

- [ ] **Step 4: `build_actions` を実装**

優先順位表([status契約](../specs/phase2-status-contract.md) §3)の順に評価する。

```python
def build_actions(ctx, model: dict, ready: dict) -> list[dict]:
    """次にできることを優先順に並べる。必ず1件以上返す。"""
    failed = {c["code"]: c["refs"] for c in ready["failed_conditions"]}
    stale = sorted(a for a, f in ctx.freshness.items() if f.state == "stale")
    loop_in_progress = bool(ctx.pending_milestones) or \
        model["structure"]["to_be"]["confirmed"] == 0

    actions: list[dict] = []

    def add(code: str, refs: list[str] | None = None, **extra) -> None:
        actions.append({"code": code, **({"refs": refs} if refs else {}), **extra})

    if ctx.pending_milestones:
        add("answer_tobe_checkpoint", ctx.pending_milestones, reason="節目で未回答")
    if objections := [r.event_id for r in ctx.responses
                      if r.reaction == "objected" and not r.subsumed_by]:
        add("resolve_objection", sorted(objections))
    if ctx.open_review_findings:
        add("address_review_findings", ctx.open_review_findings)
    if not ctx.doc.to_be and any(a.visibility == "internal" for a in ctx.doc.as_is):
        add("draft_strawman_to_be")
    if ctx.target.as_is_report_id is None:
        add("generate_as_is_report")
    if runnable := _runnable_checks(ctx):
        add("run_check", runnable)
    if open_undeterminable := failed.get("undeterminable_open"):
        add("explore_undeterminable", open_undeterminable)
    if unpromoted := _unpromoted_conflicts(ctx.doc):
        add("consider_promotion", unpromoted)
    if stale and not loop_in_progress:
        add("regenerate_stale_artifacts", stale)
    if "internal_as_is_missing" in failed:
        add("elicit_internal_as_is")
    if refs := failed.get("unsupported_confirmed_to_be"):
        add("ground_confirmed_to_be", refs)
    if _needs_discussion_slides(ctx):
        add("generate_discussion_slides")
    if refs := failed.get("to_be_go_ahead_missing"):
        add("request_to_be_go_ahead", refs)
    if stale and loop_in_progress:
        add("regenerate_stale_artifacts", stale)
    if ready["state"] == "ready":
        add("proceed_to_propose_options")
    if not actions:
        add("continue_hearing")
    return actions
```

`_runnable_checks(ctx)` は `unverified` の check のうち**対象が存在するものだけ**を返す(`CHECK_REGISTRY[name].binding == "artifact_bound"` の場合、`_current_artifact_ids` に該当typeがあること)。

`_unpromoted_conflicts(doc)` は `Gap(kind="internal_conflict")` のうち、どの `Challenge.promoted_from.ref` からも参照されていないもの。

`_needs_discussion_slides(ctx)` は最新 `as-is-report` を `derived_from` に持つ `slide_kind="discussion"` の生成物が無いときTrue。

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run pytest -v`
Expected: 全て pass(既存の `test_status.py` も含む)

- [ ] **Step 6: リントとコミット**

```bash
uv run ruff check .
git add core/src/medo_core/status.py core/tests/test_status.py
git commit -m "feat(core): 4階層診断とactionsの合成を追加

「足りない」の列挙は監査人の視点になる。同じデータを返しつつ、
Skillが最初に読むものを readiness から actions へ変える。
next_step はフェーズ1の値域のまま独立に計算し続ける。"
```

---

## Task 20: status CLIの拡張とコマンド分割

**Files:**
- Modify: `cli/src/medo_cli/main.py`
- Create: `cli/src/medo_cli/commands/__init__.py`
- Create: `cli/src/medo_cli/commands/workflow.py`
- Modify: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 19 の `project_status`
- Produces: `medo status --project <id> [--view summary|full|model|workflow|readiness|actions] [--include-scope <s,...>] [--format json|digest]`

**分割の方針**: `main.py` が肥大化するため、Task 16 で追加した進行記録の4コマンド(`check` / `review` / `respond` / `checkpoint`)を `commands/workflow.py` へ移す。`main.py` は `app.add_typer` の組み立てと既存コマンドに留める([structure.md](../../.claude/steering/structure.md) の分割ガイドに従う)。

- [ ] **Step 1: 失敗するテストを書く**

`cli/tests/test_cli.py` に追記:

```python
def test_status_defaults_to_summary_view(runner):
    _save_minimal_requirements(runner, "p1")

    result = runner.invoke(app, ["status", "--project", "p1", "--format", "json"])

    payload = json.loads(result.stdout)
    assert list(payload)[0] == "actions"


def test_status_full_view_returns_all_branches(runner):
    _save_minimal_requirements(runner, "p1")

    result = runner.invoke(app, [
        "status", "--project", "p1", "--view", "full", "--format", "json",
    ])

    payload = json.loads(result.stdout)
    assert set(payload) >= {"model", "workflow", "readiness", "actions"}


def test_status_rejects_unknown_view(runner):
    _save_minimal_requirements(runner, "p1")

    result = runner.invoke(app, ["status", "--project", "p1", "--view", "everything"])

    assert result.exit_code == 1
    assert "view" in result.stderr


def test_status_widens_scope_on_request(runner):
    _save_minimal_requirements(runner, "p1")

    result = runner.invoke(app, [
        "status", "--project", "p1", "--include-scope", "secondary", "--format", "json",
    ])

    assert result.exit_code == 0


def test_status_reports_missing_project_without_guessing(runner):
    result = runner.invoke(app, ["status", "--project", "unknown"])

    assert result.exit_code == 1
    assert "error:" in result.stderr


def test_workflow_commands_are_available_after_split(runner):
    """分割後もコマンド体系は変わらない(Skill契約を壊さない)。"""
    result = runner.invoke(app, ["check", "--help"])

    assert result.exit_code == 0
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest cli/tests/test_cli.py -k status -v`
Expected: FAIL — `no such option: --view`

- [ ] **Step 3: CLIを実装**

```python
VIEWS = ("summary", "full", "model", "workflow", "readiness", "actions")


@app.command("status")
def status(
    project: str = typer.Option(..., "--project"),
    view: str = typer.Option("summary", "--view", help=f"表示範囲: {' | '.join(VIEWS)}"),
    include_scope: str = typer.Option(
        "", "--include-scope", help="診断対象に加えるscope(secondary,out)"
    ),
    format_: str = typer.Option("json", "--format", help="json|digest"),
) -> None:
    """現在地と次にできることを返す。"""
    if view not in VIEWS:
        raise ValueError(f"不明な view です: {view}(有効: {', '.join(VIEWS)})")
    if format_ not in ("json", "digest"):
        raise ValueError(f"不明な format です: {format_}")
    scopes = ("core",)
    for s in (v.strip() for v in include_scope.split(",") if v.strip()):
        if s not in ("secondary", "out"):
            raise ValueError(f"不明な scope です: {s}(有効: secondary, out)")
        scopes += (s,)
    payload = project_status(get_storage(), project, view=view, include_scope=scopes)
    if format_ == "json":
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _echo_digest(payload)
```

`_echo_digest` は `actions` を先頭に1行ずつ出力し、続けて `diagnostic_phase` / `round_delta` / `checkpoint` を要約する。

**既定の `--format` は `json` のまま変えない**。フェーズ1のSkillはオプションなしの `medo status` がJSONを返す前提で書かれている。

進行記録コマンドを `commands/workflow.py` へ移し、`main.py` からは登録のみ行う。**`commands/workflow.py` は `main.py` を import しない** — `get_storage` は `medo_core.config` から、`_fail` は `commands/_common.py` へ切り出して両者が参照する(逆流を避ける):

```python
# cli/src/medo_cli/main.py
from medo_cli.commands import workflow as workflow_commands

app.add_typer(workflow_commands.check_app, name="check")
app.add_typer(workflow_commands.review_app, name="review")
app.add_typer(workflow_commands.respond_app, name="respond")
app.add_typer(workflow_commands.checkpoint_app, name="checkpoint")
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest -v`
Expected: 全て pass

- [ ] **Step 5: リントとコミット**

```bash
uv run ruff check .
git add cli/src/medo_cli/ cli/tests/test_cli.py
git commit -m "feat(cli): statusのprojectionとコマンド分割

Skillは開始・終了ごとにstatusを呼ぶため、毎回全量を返すと累積コストになる。
単一コマンドを維持したまま返す範囲を絞る。"
```

---

## Task 21: ドキュメント同期と手動スモーク

**Files:**
- Modify: `.claude/steering/structure.md`
- Modify: `.claude/steering/tech.md`
- Create: `.claude/specs/phase2/spec.md`
- Create: `.claude/specs/phase2/tasks.md`
- Modify: `docs/usage.md`

**Interfaces:**
- Consumes: Task 1〜20 の完成した実装

- [ ] **Step 1: ストレージパス表を更新**

`.claude/steering/structure.md` §5 に3行追加する:

| パス | 内容 |
|---|---|
| `projects/{id}/events/{ev_id}` | 進行記録(追記のみ。要件の版とは独立) |
| `projects/{id}/manifests/v{n}` | 変更manifest(セクション別の実質変更宣言) |
| `projects/{id}/meta/id_watermark` | ID採番簿(プレフィックス別の high-water mark) |

同 §2 のモジュール一覧に `nodes.py` / `watermark.py` / `manifest.py` / `events.py` / `workflow.py` / `checks.py` / `responses.py` / `diagnostics.py` / `context.py` を追加する。§8 の分割ガイドに `cli/src/medo_cli/commands/` を追記する。

- [ ] **Step 2: コマンド一覧を更新**

`.claude/steering/tech.md` §6 に、Task 16・20で追加したコマンドを追加する。§5 の環境変数表に `MEDO_TRACE`(既定なし。設定するとCLI呼び出し列をJSONLで追記)を追加する。

`.claude/steering/testing.md` の「Skill evalケース」を差し替える。現行は「実案件1件を目視確認」だが、これではホスト間の差が見えない。**同じ初期状態から各ホストに1周させ、`MEDO_TRACE` のトレースをdiffする**手順に改める(Task 22)。

- [ ] **Step 3: フェーズ2のAgent向け要約を作る**

`.claude/specs/phase2/spec.md` は正本([medo-phase2-design.md](../specs/medo-phase2-design.md))へのポインタと、標準周回4ステージ・不変条件7だけを持つ要約とする(二重管理を避ける)。`tasks.md` は本計画のTask 1〜21(19bを含む22件)のチェックリストを持つ。

- [ ] **Step 4: 手動スモークを実行して結果を記録**

実案件(`medo-ops`)に対して標準周回を1周させ、以下を確認する。**自動テストでは検出できない、実データでの通し動作を見る**:

**2回に分けて保存する**。ID初回採番と内容追加を同じ保存で行うと `id_only_migration` が立たず、確認項目2を検証できない。

```bash
export MEDO_BACKEND=local
uv run medo status --project medo-ops --format json | head -40

# 1回目: 読んでそのまま保存する(ID採番のみ)
uv run medo requirements get --project medo-ops --format json > /tmp/req.json
uv run medo requirements save --project medo-ops --file /tmp/req.json
uv run medo status --project medo-ops --view model   # 生成物がstaleになっていないこと

# 2回目: as_is に internal を1件足して保存
#   (/tmp/req.json を編集。既存ノードのIDは書き換えない)
uv run medo requirements save --project medo-ops --file /tmp/req.json
uv run medo status --project medo-ops                # actions先頭が節目回答か

# 標準周回を1周させる: 出力 → レビュー → ぶつける → 振り返る
uv run medo artifacts save --project medo-ops --type as-is-report \
  --requirements-version 2 --generated-by claude --file /tmp/as-is-report.md
uv run medo artifacts save --project medo-ops --type slides --slide-kind discussion \
  --derived-from as-is-report-v1 --requirements-version 2 \
  --generated-by claude --file /tmp/slides.md
uv run medo check add --project medo-ops --check reality_gap --result completed
uv run medo review add --project medo-ops --report as-is-report-v1 \
  --slides slides-v1 --outcome approved --reviewed-by human
uv run medo respond add --project medo-ops --stakeholder sh-1 \
  --artifact as-is-report-v1 --purpose as_is_alignment --reaction empathized
uv run medo checkpoint answer --project medo-ops --responds-to <ev-N> --answer generate
uv run medo status --project medo-ops --view full    # round_delta が非空か
```

確認項目:

1. フェーズ1の既存データ(課題5件・open_questions)が読め、初回保存でID採番される
2. その保存の manifest に `id_only_migration: true` が立ち、生成物が stale にならない
3. `internal` な AsIs を追加した保存で `MilestoneDetected` が記録される
4. `medo status` の `actions` 先頭が `answer_tobe_checkpoint` になる
5. `next_step` がフェーズ1の値域のまま返る
6. **討議用スライドを保存すると `expression_safety` が `run_check` に現れる**(対象が無い間は出ない)
7. **`review add` が `--slides` の親子関係を検証する**(無関係なスライドIDを渡すと失敗する)
8. **1周させた後の `round_delta` が非空になり、`progress_count` が0でない**

**結果を `docs/setup.md` に追記する**(失敗した項目は失敗として記録し、推測で補完しない)。

- [ ] **Step 5: リントとコミット**

```bash
uv run pytest
uv run ruff check .
git add .claude/ docs/
git commit -m "docs: フェーズ2決定論層の完成に伴う参照先を同期

ストレージパスとモジュール構成が変わったため、新規ファイルの
置き場所ガイドが実態とずれる。"
```

---

## Task 22: CLIコールトレース(Skill再現性の計測)

**Files:**
- Create: `cli/src/medo_cli/trace.py`
- Create: `cli/tests/test_trace.py`
- Modify: `cli/src/medo_cli/main.py`
- Modify: `cli/pyproject.toml`

**Interfaces:**
- Consumes: なし(既存CLIに横断的に付ける)
- Produces: `Tracer.from_env() -> Tracer | None` / `Tracer.record(argv, exit_code)` / `medo_cli.main:main` を console_script のエントリポイントにする

**なぜ必要か**: Skillは手順書であり、どのホスト(Claude / Codex / agy)がどのモデルで実行するかで挙動が変わる。**「事実は縛る」はCLIが担保するが、Skillが必要なCLI呼び出しを飛ばしたことは検出できない** — 飛ばしても残りのコマンドは正常終了するため。

状態がすべてCLIにある(移植性の条件1)という性質上、**Skillが実行したCLI呼び出しの列は決定論的な成果物**である。同じ初期状態から各ホストに1周させてトレースを突き合わせれば、「再現性が気になる」を「agyは `facts save` を飛ばす傾向がある」という修正可能な事実に変えられる。現行の `testing.md` は「実案件1件を目視確認」としており、ホスト間の差が見えない。

- [ ] **Step 1: 失敗するテストを書く**

`cli/tests/test_trace.py`:

```python
import json

from medo_cli.trace import Tracer


def test_disabled_when_env_is_unset(monkeypatch):
    monkeypatch.delenv("MEDO_TRACE", raising=False)

    assert Tracer.from_env() is None


def test_records_command_and_exit_code(tmp_path, monkeypatch):
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["status", "--project", "p1"], exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["command"] == ["status"]
    assert entry["exit_code"] == 0


def test_appends_so_a_whole_round_forms_one_trace(tmp_path, monkeypatch):
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))
    tracer = Tracer.from_env()

    tracer.record(["status", "--project", "p1"], exit_code=0)
    tracer.record(["check", "add", "--project", "p1"], exit_code=0)

    assert [json.loads(x)["command"] for x in path.read_text(encoding="utf-8").splitlines()] == [
        ["status"], ["check", "add"]
    ]


def test_keeps_values_of_decision_relevant_options(tmp_path, monkeypatch):
    """どの選択肢を選んだかはホスト間比較の対象なので値を残す。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(
        ["check", "add", "--check", "reality_gap", "--result", "undeterminable",
         "--disposition", "promoted"],
        exit_code=0,
    )

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"]["--result"] == "undeterminable"
    assert entry["options"]["--disposition"] == "promoted"


def test_redacts_free_text_values(tmp_path, monkeypatch):
    """顧客の生の声がトレースに残ると、リポジトリ外に出せなくなる。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(
        ["facts", "save", "--statement", "A社は年間3億円を紙処理に費やしている"],
        exit_code=0,
    )

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"]["--statement"] == "<redacted>"


def test_redacts_file_paths(tmp_path, monkeypatch):
    """パスに顧客名が含まれうる。"""
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["requirements", "save", "--file", "/home/x/A社/req.json"],
                             exit_code=0)

    entry = json.loads(path.read_text(encoding="utf-8").strip())
    assert entry["options"]["--file"] == "<redacted>"


def test_records_failures_so_skipped_recovery_is_visible(tmp_path, monkeypatch):
    path = tmp_path / "trace.jsonl"
    monkeypatch.setenv("MEDO_TRACE", str(path))

    Tracer.from_env().record(["status", "--project", "unknown"], exit_code=1)

    assert json.loads(path.read_text(encoding="utf-8").strip())["exit_code"] == 1


def test_never_raises_when_trace_path_is_unwritable(tmp_path, monkeypatch):
    """計測機構が本来の作業を止めてはならない。"""
    monkeypatch.setenv("MEDO_TRACE", str(tmp_path / "missing" / "trace.jsonl"))

    Tracer.from_env().record(["status"], exit_code=0)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest cli/tests/test_trace.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_cli.trace'`

- [ ] **Step 3: `trace.py` を実装**

```python
"""CLI呼び出し列の記録。Skillの再現性をホスト間で比較するための計測機構。

状態がすべてCLIにあるため、呼び出し列は決定論的な成果物になる。同じ初期状態から
各ホストに1周させてトレースを突き合わせると、Skillが飛ばした操作が見える。
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

# 値を残すオプション。「どの選択肢を選んだか」はホスト間比較の対象になる。
# ここに無いオプションの値は伏せる(顧客の生の声・ファイルパスが混ざるため)。
VALUE_SAFE_OPTIONS = frozenset({
    "--type", "--slide-kind", "--result", "--check", "--purpose", "--reaction",
    "--outcome", "--disposition", "--answer", "--view", "--format", "--kind",
    "--include-scope", "--editorial", "--generated-by", "--reviewed-by",
    "--requirements-version", "--responds-to", "--stakeholder", "--artifact",
    "--report", "--slides", "--derived-from", "--covers", "--focus", "--refs",
    "--from-artifact",
})


class Tracer:
    def __init__(self, path: Path):
        self._path = path

    @classmethod
    def from_env(cls) -> "Tracer | None":
        raw = os.environ.get("MEDO_TRACE")
        return cls(Path(raw)) if raw else None

    def record(self, argv: list[str], exit_code: int) -> None:
        entry = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "command": _command(argv),
            "options": _options(argv),
            "exit_code": exit_code,
        }
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # 計測が本来の作業を止めない


def _command(argv: list[str]) -> list[str]:
    """先頭からオプションが現れるまでの語をコマンド名とする。

    clickはサブコマンドをオプションより前に取るため、最初のオプション以降の
    非オプション語はすべてオプションの値である(`--project p1` の `p1` など)。
    """
    words: list[str] = []
    for token in argv:
        if token.startswith("-"):
            break
        words.append(token)
    return words[:2]


def _options(argv: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    for i, token in enumerate(argv):
        if not token.startswith("--"):
            continue
        value = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else ""
        options[token] = value if token in VALUE_SAFE_OPTIONS else "<redacted>"
    return options
```

**`_command` が最初のオプションで打ち切るのは、`--project p1` の `p1` を拾わないため**。argv全体から非オプション語を集めると、オプションの値がコマンド名に混入する。先頭2語までとするのは `medo check add` のサブコマンド2階層に合わせるため。

- [ ] **Step 4: エントリポイントを `main()` に変える**

現行の console_script は `medo_cli.main:app` を直指ししており、終了コードを観測できない。ラッパーを挟む。

`cli/src/medo_cli/main.py` の末尾:

```python
def main() -> None:
    """console_script のエントリポイント。MEDO_TRACE 指定時は呼び出しを記録する。"""
    tracer = Tracer.from_env()
    code = 0
    try:
        app()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        raise
    finally:
        if tracer:
            tracer.record(sys.argv[1:], exit_code=code)


if __name__ == "__main__":
    main()
```

`cli/pyproject.toml`:

```toml
[project.scripts]
medo = "medo_cli.main:main"
```

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run pytest -v`
Expected: 全て pass

- [ ] **Step 6: リントとコミット**

```bash
uv run ruff check .
git add cli/src/medo_cli/trace.py cli/tests/test_trace.py cli/src/medo_cli/main.py cli/pyproject.toml
git commit -m "feat(cli): CLIコールトレースを追加

Skillが必要な操作を飛ばしたことは、残りのコマンドが正常終了するため
検出できない。状態がすべてCLIにある性質を使い、呼び出し列を
ホスト間で突き合わせられるようにする。

顧客の生の声とファイルパスは伏せる。トレースをリポジトリやIssueに
貼れなくなると、比較そのものが回らないため。"
```

---

## 完了の定義

- [ ] `uv run pytest` が全て通る
- [ ] `uv run ruff check .` が通る
- [ ] `medo status --view full` が4階層(`model` / `workflow` / `readiness` / `actions`)を返す
- [ ] フェーズ1のSkill(`medo-hearing` / `medo-propose-options` / `medo-grow-prfaq`)が `next_step` の値域変更なしに動く
- [ ] 実案件1件で標準周回を1周させ、節目の記録と `actions` の変化を確認した(Task 21 Step 4)
- [ ] `medo requirements save` が `WorkflowRecorder` 経由で節目を記録する(Task 16 Step 4)
- [ ] `medo artifacts save` の既存オプション(`--cites` / `--cites-facts` / `--options` / `--grown-from`)がすべて残っている
- [ ] `project_status` の既存呼び出し(`knowledge_root` 位置引数・要件なしで `next_step: "hearing"`)が壊れていない
- [ ] `MEDO_TRACE` を設定して1周させると、CLI呼び出し列がJSONLで得られる(Task 22)

## 相互レビューの照合

2者のレビューは**観点を分けて実施した**(Codex=実装可能性、agy=設計の取りこぼしと目的整合)。両者が同じ問題を別の言葉で指摘した箇所と、片方しか見つけなかった箇所を以下に残す。

| # | 指摘 | Codex | agy | 判定 |
|---|---|---|---|---|
| 1 | Task 19が実装不能(実装手順が無い) | 重大 | — | Codex単独。19/19bへ分割 |
| 2 | 既存CLI契約の破壊(`--cites` / `--grown-from` 消失) | 重大 | — | Codex単独。追加のみに戻した |
| 3 | `diff()` が pydantic モデルを `set()` に入れる | 重大 | — | Codex単独 |
| 4 | 初回manifestが全セクション変更扱い | 重大 | — | Codex単独 |
| 5 | `--editorial` でノード追加まで隠せる | 重大 | — | Codex単独 |
| 6 | `freshness()` が引用ファクトの鮮度を見ない | 重大 | — | Codex単独 |
| 7 | CLI要件保存が `WorkflowRecorder` を経由しない | 重大 | — | Codex単独。実利用で節目が記録されない |
| 8 | `Bottleneck.confidence` / `from_hypothesis` の検証欠落 | 重大(5に含む) | 軽微 | **両者一致** |
| 9 | `detect_ritualized` が変更のあった周回のみを母数にする | 軽微 | 軽微 | **両者一致** |
| 10 | 往復中は `regenerate_stale_artifacts` の順位を下げる | — | 軽微 | 計画に既出。agyは縮約版で見えず |
| 11 | `RejectedOption` が `Artifact` に無い | — | 重大 | **agy単独**。設計にあり実在 |
| 12 | スモークが標準周回を1周していない | 重大(16) | 軽微 | **両者一致**(観点は別) |
| 13 | `disposition` の更新手段が非自明 | — | 軽微 | agy単独。追記で対応 |

**agyの重大2・3と軽微1〜3は誤検出**だった。5,900行では2度タイムアウトしたためコードブロックを削った骨子を渡したが、`journey_before` / `--focus` / `--disposition` / `confirmed` 検証は削った側にあり、agyには欠落に見えていた。レビュー材料の作り方の失敗であってagyの判断の誤りではない。

**Codexが実装可能性、agyが設計整合という分担は機能した**。Codexの重大7件はagyが1件も検出せず、agyが見つけた `RejectedOption` の欠落はCodexが検出しなかった。同じ計画を同じ観点で2度読ませるより、観点を分けたほうが被覆が広い。

---

## 本計画の範囲外

| 項目 | 理由 |
|---|---|
| Skill 4本(`medo-investigate` / `review` / `dialogue` / `decide`)+ 討議用スライド生成 | 優先度5。本体がSKILL.md本文であり計画の形が異なる。本計画の `actions` 契約が実データで確定してから着手する |
| 最終提案スライド + `phase_signoff` ゲート | 優先度6。`prfaq` が前提 |
| 出典検証の強化(URLフェッチ + 数値突合) | 並行項目だが詳細設計が未了([設計索引](../specs/medo-phase2-design.md#詳細設計が未了の項目)) |
| ナレッジ来歴 / `knowledge-digest` / `decision-roadmap` / pricing / `build-mock` / `propose-architecture` / 簡易Webアプリ | 後続。いずれも詳細正本を持たない |
| Firestoreでの採番簿トランザクション | `Storage` プロトコルへの `transact` 追加が要る。利用スコープが本人のみ(不変条件5)で同時保存が起きないため見送る。Firestoreを複数プロセスから使う段階で対応する |
