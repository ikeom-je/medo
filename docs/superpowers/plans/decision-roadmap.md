# decision-roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `medo status --view uncertainty` で、次に潰すべき不確実性を並べる。策を2〜3つ(メイン/サブ、松竹梅)持たせ、策を分けるパラメタの切り替え点をコードが逆算し、決め手の仮説を Jev の分類で見つける。

**Architecture:** core は決定論だけを持つ(策とパラメタのスキーマと保存時検査、`FermiModel.unit`、感度・切り替え点・波及範囲・並べ方の純関数、`add_alternative_option` の action)。Jev の呼び出しと、Jev の判定を合わせたビューの組み立ては cli に置く。Skill は propose-options(策を2〜3つ作る)と decide(最上位の問いを焦点の候補にする)を更新する。

**Tech Stack:** Python 3.12 / pydantic 2 / typer / pytest / ruff / TypeSafe System One(Jev)/ 既存の `fermi.evaluate`

**Spec:** `docs/superpowers/specs/phase2-decision-roadmap.md`(承認済み)

## Global Constraints

- 出力は呼ぶたびに計算するビュー。生成物として保存しない(spec §1)
- 策は最大3つ。tier の上限: `main` ≤1、`sub` ≤2、`matsu`/`take`/`ume` 各 ≤1、系の混在は不可。**策が1つでも保存は拒否しない**(spec §4.1、不変条件6)
- 策を分けるパラメタは名前で推測しない。`pivot` / `pivot_unit` / 策ごとの `pivot_variable` を明示し、対応する変数はすべての策で `assume`(spec §3.2)
- 切り替え点は最上位の策が入れ替わる境目だけ。区間幅が相対 1e-3 まで二分法。不連続は「いずれかの策の値が絶対 1e-9 または相対 1e-2 を超えて跳ぶ」、決めきれなければ判定不能。結果は近似と明記(spec §3.3)
- 探索範囲: 明示 `pivot_range`(有限、下限<上限。下限>0 なら対数、それ以外は線形)、無ければ仮定値から(すべて正なら [min/10, max×10] 対数、0・負を含めば [min−幅, max+幅] 線形)、200点(spec §3.3)
- 策どうしの比較は `FermiModel.unit` が同じで空でないときだけ。一部の策の計算が失敗したら全策の比較はしない(spec §3.3・§6.3)
- 波及範囲は `determines` の辺だけをたどり、強連結成分はひとまとまり。Jev なしは `unknown`、未確定事項は `not_applicable`(spec §3.1)
- 並べ方: 有効な切り替え点 > 波及範囲 > 振れ幅の比 > decision_relevant ≥0.5 > 手間 > ID(spec §6.1)
- Jev: 鍵なし → `judge: unavailable`(終了0)、鍵ありで失敗 → 非ゼロ終了(spec §6.4)
- core は Jev を呼ばない。コードコメントは Why not のみ。CLI失敗は非ゼロ終了+`error:`
- Codex への委譲は `codex exec -m gpt-6.1-sol -c model_reasoning_effort=high ... </dev/null`。テストと ruff の最終確認は Claude の環境で行う

## Review Focus

1. **既存の mini-prfaq / fermi の読み込み**: 新フィールドの無い保存データがそのまま読め、ビューが「pivot が無い」と理由付きで返すこと → Task 1 `test_legacy_mini_prfaq_loads` / Task 4 `test_view_without_pivot_reports_reason`
2. **3策で最上位でない策どうしの交点**: 切り替え点に数えないこと → Task 3 `test_switch_ignores_crossing_below_top`
3. **`1/(x-1)` 型の不連続**: 交点と誤認せず `discontinuity` を返すこと → Task 3 `test_switch_reports_discontinuity`
4. **策が1つの mini-prfaq**: 保存でき、ビューが「比べられない」、status に `add_alternative_option` → Task 1 / Task 4
5. **`--options` の手法名にコロンを含む既存の使い方**: 新オプション導入後も手法名が変わらないこと → Task 6 `test_options_with_colon_in_approach_unchanged`

---

## File Structure

| ファイル | 責務 |
|---|---|
| `core/src/medo_core/artifacts.py`(変更) | `OptionMeta.tier` / `fermi` / `pivot_variable`、`Artifact.pivot` / `pivot_unit` / `pivot_range`、保存対象だけへの検査 |
| `core/src/medo_core/fermi.py`(変更) | `FermiModel.unit` |
| `core/src/medo_core/uncertainty.py`(新規) | 探索範囲、感度、切り替え点、候補の組、波及範囲、並べ方(純関数) |
| `core/src/medo_core/status.py`(変更) | `add_alternative_option` |
| `cli/src/medo_cli/jev.py`(変更) | `judge_uncertainty`(implies / decision_relevant / effort) |
| `cli/src/medo_cli/commands/uncertainty.py`(新規) | ビューの組み立て(fermi の読み込みと再計算、Jev、並べ方) |
| `cli/src/medo_cli/main.py`(変更) | `status --view uncertainty` の振り分け、`artifacts save` の新オプション |
| `scripts/eval/implies_cases.json` / `run_implies_eval.py`(新規) | 評価セットと評価 |
| `skills/src/medo-propose-options` / `medo-decide`(変更) | 手順 |

---

## Part A: core

### Task 1: 策とパラメタのスキーマ・保存時の検査・FermiModel.unit

**Files:**
- Modify: `core/src/medo_core/artifacts.py`, `core/src/medo_core/fermi.py`
- Test: `core/tests/test_artifacts.py`, `core/tests/test_fermi.py`

**Interfaces:**
- Produces:
  - `OptionMeta.tier: Literal["", "main", "sub", "matsu", "take", "ume"] = ""`、`fermi: str = ""`、`pivot_variable: str = ""`
  - `Artifact.pivot: str = ""`、`pivot_unit: str = ""`、`pivot_range: tuple[float, float] | None = None`
  - `ArtifactStore.save` が mini-prfaq の保存対象に `_validate_options(artifact)` をかける(`ValueError`)
  - `FermiModel.unit: str = ""`

- [ ] **Step 1: Write the failing tests**

```python
def _mini(options, **kw):
    return Artifact(project="p1", type="mini-prfaq", requirements_version=1, content="候補",
                    generated_by="claude", options=options, **kw)


def test_legacy_mini_prfaq_loads(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    storage.put("projects/p1/artifacts/mini-prfaq-v1", {
        "project": "p1", "type": "mini-prfaq", "version": 1, "requirements_version": 1,
        "content": "x", "options": [{"name": "A", "approach_type": "既存解決"}]})
    a = ArtifactStore(storage).get("p1", "mini-prfaq-v1")
    assert a.options[0].tier == "" and a.pivot == ""


def test_single_option_is_saved(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    assert store.save("p1", _mini([OptionMeta(name="A", tier="main")])) == "mini-prfaq-v1"


@pytest.mark.parametrize("tiers", [
    ["main", "main"], ["sub", "sub", "sub"], ["matsu", "matsu"], ["main", "matsu"]])
def test_invalid_tier_sets_are_rejected(tmp_path, tiers):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    with pytest.raises(ValueError):
        store.save("p1", _mini([OptionMeta(name=f"o{i}", tier=t) for i, t in enumerate(tiers)]))


def test_four_options_are_rejected(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    with pytest.raises(ValueError, match="最大3"):
        store.save("p1", _mini([OptionMeta(name=f"o{i}") for i in range(4)]))


def test_pivot_requires_variable_for_every_option_with_fermi(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    opts = [OptionMeta(name="A", fermi="fermi-v1", pivot_variable="rate"),
            OptionMeta(name="B", fermi="fermi-v2")]
    with pytest.raises(ValueError, match="pivot_variable"):
        store.save("p1", _mini(opts, pivot="利用率", pivot_unit="比率"))


@pytest.mark.parametrize("rng", [(1.0, 1.0), (2.0, 1.0), (float("inf"), 2.0)])
def test_invalid_pivot_range_is_rejected(tmp_path, rng):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    with pytest.raises(ValueError, match="pivot_range"):
        store.save("p1", _mini([OptionMeta(name="A")], pivot="x", pivot_range=rng))


def test_duplicate_option_names_rejected_when_tiers_used(tmp_path):
    store = ArtifactStore(LocalJsonStorage(tmp_path))
    with pytest.raises(ValueError, match="一意"):
        store.save("p1", _mini([OptionMeta(name="A", tier="main"), OptionMeta(name="A", tier="sub")]))
```

`test_fermi.py`:

```python
def test_fermi_model_unit_defaults_to_empty():
    m = FermiModel.model_validate({"name": "n", "variables": {"x": {"assume": 1}}, "formula": "x"})
    assert m.unit == ""
```

(`OptionMeta` / `Artifact` の import と、既存の `_artifact` ヘルパーがあればそれに合わせる)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest core/tests/test_artifacts.py core/tests/test_fermi.py -k "tier or option or pivot or legacy_mini or unit" -v`
Expected: FAIL(フィールド未定義)

- [ ] **Step 3: Write minimal implementation**

```python
Tier = Literal["", "main", "sub", "matsu", "take", "ume"]
_TIER_LIMITS = {"main": 1, "sub": 2, "matsu": 1, "take": 1, "ume": 1}
_TIER_FAMILY = {"main": "ms", "sub": "ms", "matsu": "mtu", "take": "mtu", "ume": "mtu"}


class OptionMeta(BaseModel):
    name: str
    approach_type: str = ""
    tier: Tier = ""
    fermi: str = ""
    pivot_variable: str = ""


# Artifact に追加
    pivot: str = ""
    pivot_unit: str = ""
    pivot_range: tuple[float, float] | None = None


def _validate_options(artifact: Artifact) -> None:
    # 保存対象だけを検査する。既存データの読み込みでは検査しない(spec §4.1)。
    if artifact.type != "mini-prfaq":
        return
    opts = artifact.options
    if len(opts) > 3:
        raise ValueError("策は最大3つです(松竹梅)")
    tiers = [o.tier for o in opts if o.tier]
    for tier, limit in _TIER_LIMITS.items():
        if tiers.count(tier) > limit:
            raise ValueError(f"tier {tier} は {limit} つまでです")
    if len({_TIER_FAMILY[t] for t in tiers}) > 1:
        raise ValueError("main/sub と松竹梅を混ぜられません")
    if (tiers or any(o.fermi or o.pivot_variable for o in opts)) and len(
            {o.name for o in opts}) != len(opts):
        raise ValueError("策の名前は一意である必要があります")
    if artifact.pivot:
        missing = [o.name for o in opts if o.fermi and not o.pivot_variable]
        if missing:
            raise ValueError(f"pivot を指定したら fermi を持つ策すべてに pivot_variable が要ります: {missing}")
    if artifact.pivot_range is not None:
        lo, hi = artifact.pivot_range
        if not (math.isfinite(lo) and math.isfinite(hi) and lo < hi):
            raise ValueError("pivot_range は有限で 下限 < 上限 である必要があります")
```

`ArtifactStore.save` の冒頭(`existing` を作った直後)で `_validate_options(artifact)` を呼ぶ。`fermi.py` の `FermiModel` に `unit: str = ""`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check .`
Expected: PASS(既存テストも)

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/artifacts.py core/src/medo_core/fermi.py core/tests/test_artifacts.py core/tests/test_fermi.py
git commit -m "feat(core): 策の役割と策を分けるパラメタを mini-prfaq に持たせる"
```

### Task 2: 探索範囲と感度

**Files:**
- Create: `core/src/medo_core/uncertainty.py`
- Test: `core/tests/test_uncertainty.py`

**Interfaces:**
- Consumes: `FermiModel`, `evaluate`(既存)、`Fact`
- Produces:
  - `search_grid(assumed: list[float], explicit: tuple[float, float] | None, points: int = 200) -> list[float]`
  - `Strategy(BaseModel)`: `name: str`, `tier: str`, `model: FermiModel`, `variable: str`
  - `value_at(s: Strategy, facts: dict[str, Fact], x: float) -> float | None`(計算失敗は None)
  - `sensitivity(s: Strategy, facts, grid) -> dict`(`{"swing": float, "ratio": float | None, "base": float}`)

- [ ] **Step 1: Write the failing tests**

```python
def _s(name, formula, x=1.0, unit="万円", tier="main"):
    model = FermiModel(name=name, unit=unit, formula=formula,
                       variables={"x": FermiVar(assume=x), "k": FermiVar(assume=2.0)})
    return Strategy(name=name, tier=tier, model=model, variable="x")


def test_grid_positive_is_log_spanning_tenfold():
    g = search_grid([1.0, 4.0], None)
    assert len(g) == 200 and g[0] == pytest.approx(0.1) and g[-1] == pytest.approx(40.0)
    assert g[1] / g[0] == pytest.approx(g[2] / g[1])


def test_grid_with_zero_or_negative_is_linear():
    g = search_grid([-1.0, 3.0], None)
    assert g[0] == pytest.approx(-5.0) and g[-1] == pytest.approx(7.0)
    assert g[1] - g[0] == pytest.approx(g[2] - g[1])


def test_grid_explicit_range_log_if_positive_else_linear():
    assert search_grid([5.0], (0.01, 1.0))[0] == pytest.approx(0.01)
    lin = search_grid([5.0], (0.0, 1.0))
    assert lin[1] - lin[0] == pytest.approx(lin[2] - lin[1])


def test_sensitivity_ratio_none_when_base_zero():
    s = _s("A", "x - 1", x=1.0)
    out = sensitivity(s, {}, search_grid([1.0], None))
    assert out["base"] == 0 and out["ratio"] is None and out["swing"] > 0


def test_sensitivity_uses_abs_base():
    s = _s("A", "0 - x * k", x=1.0)
    out = sensitivity(s, {}, search_grid([1.0], None))
    assert out["ratio"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest core/tests/test_uncertainty.py -v`
Expected: FAIL(`ModuleNotFoundError`)

- [ ] **Step 3: Write minimal implementation**

```python
"""次に潰すべき不確実性の決定論部分。Jevの判定は呼び出し側から受け取る。"""

from __future__ import annotations

import math

from pydantic import BaseModel

from medo_core.facts import Fact
from medo_core.fermi import FermiModel, FermiVar, evaluate


class Strategy(BaseModel):
    name: str
    tier: str = ""
    model: FermiModel
    variable: str


def _log(lo, hi, n):
    r = (hi / lo) ** (1 / (n - 1))
    return [lo * r**i for i in range(n)]


def _lin(lo, hi, n):
    step = (hi - lo) / (n - 1)
    return [lo + step * i for i in range(n)]


def search_grid(assumed, explicit, points=200):
    if explicit is not None:
        lo, hi = explicit
        return _log(lo, hi, points) if lo > 0 else _lin(lo, hi, points)
    lo, hi = min(assumed), max(assumed)
    if lo > 0:
        return _log(lo / 10, hi * 10, points)
    span = (hi - lo) or max(abs(lo), abs(hi), 1.0)
    return _lin(lo - span, hi + span, points)


def value_at(s, facts, x):
    variables = {**s.model.variables, s.variable: FermiVar(assume=x)}
    try:
        return evaluate(s.model.model_copy(update={"variables": variables}), facts).value
    except (ValueError, ZeroDivisionError, OverflowError):
        return None


def sensitivity(s, facts, grid):
    base = value_at(s, facts, s.model.variables[s.variable].assume)
    values = [v for x in grid if (v := value_at(s, facts, x)) is not None]
    swing = (max(values) - min(values)) if values else 0.0
    ratio = None if not base else swing / abs(base)
    return {"swing": swing, "ratio": ratio, "base": base}
```

(`evaluate` が 0除算で `ZeroDivisionError` 以外を投げる場合は、既存の fermi の例外型に合わせて捕まえる)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest core/tests/test_uncertainty.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/uncertainty.py core/tests/test_uncertainty.py
git commit -m "feat(core): 策を分けるパラメタの探索範囲と感度"
```

### Task 3: 切り替え点

**Files:**
- Modify: `core/src/medo_core/uncertainty.py`
- Test: `core/tests/test_uncertainty.py`

**Interfaces:**
- Consumes: `Strategy` / `value_at` / `search_grid`(Task 2)
- Produces: `switch_points(strategies: list[Strategy], facts, grid) -> dict` を返す。キー:
  - `points: list[dict]`(`{"at": float, "from": str, "to": str}`。from は値が小さい側で上だった策)
  - `discontinuities: list[dict]`(`{"near": float, "strategy": str}`)
  - `undetermined: list[float]`
  - `excluded: list[float]`(計算失敗の格子点)
  - `always_top: str | None`(入れ替わりが無いとき、その策の名前)
  - `error: str`(比較できない理由。空なら比較した)

- [ ] **Step 1: Write the failing tests**

```python
def test_switch_between_two_linear_strategies():
    a, b = _s("A", "x * 10", x=1.0), _s("B", "20 + x * 0", x=1.0, tier="sub")
    out = switch_points([a, b], {}, search_grid([1.0], (0.0, 5.0)))
    assert len(out["points"]) == 1
    p = out["points"][0]
    assert p["at"] == pytest.approx(2.0, rel=1e-2) and (p["from"], p["to"]) == ("B", "A")


def test_switch_ignores_crossing_below_top():
    # A と C は x=0 で交わるが、その付近では B(0.1)が最上位なので A→C は切り替え点ではない
    a = _s("A", "0 - x", x=1.0)
    b = _s("B", "0.1 + x * 0", x=1.0, tier="sub")
    c = _s("C", "x", x=1.0, tier="sub")
    out = switch_points([a, b, c], {}, search_grid([1.0], (-1.0, 1.0)))
    assert [(p["from"], p["to"]) for p in out["points"]] == [("A", "B"), ("B", "C")]
    assert [p["at"] for p in out["points"]] == [pytest.approx(-0.1, rel=1e-2),
                                                 pytest.approx(0.1, rel=1e-2)]


def test_switch_reports_discontinuity():
    a = _s("A", "1 / (x - 1)", x=2.0)
    b = _s("B", "0 + x * 0", x=2.0, tier="sub")
    out = switch_points([a, b], {}, search_grid([2.0], (0.0, 3.0)))
    assert any(abs(d["near"] - 1.0) < 0.05 for d in out["discontinuities"])
    assert all(abs(p["at"] - 1.0) > 0.05 for p in out["points"])


def test_switch_no_change_reports_always_top_as_approximation():
    a, b = _s("A", "x + 10", x=1.0), _s("B", "x", x=1.0, tier="sub")
    out = switch_points([a, b], {}, search_grid([1.0], None))
    assert out["points"] == [] and out["always_top"] == "A"


def test_switch_requires_same_nonempty_unit():
    a, b = _s("A", "x", unit="万円"), _s("B", "x", unit="件", tier="sub")
    assert "unit" in switch_points([a, b], {}, search_grid([1.0], None))["error"]


def test_switch_fails_whole_comparison_when_one_strategy_never_evaluates():
    a = _s("A", "x")
    b = _s("B", "x / 0", tier="sub")
    out = switch_points([a, b], {}, search_grid([1.0], None))
    assert out["error"] and out["points"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest core/tests/test_uncertainty.py -k switch -v`
Expected: FAIL(`switch_points` 未定義)

- [ ] **Step 3: Write minimal implementation**

```python
_ABS_JUMP = 1e-9
_REL_JUMP = 1e-2
_REL_WIDTH = 1e-3


def _values(strategies, facts, x):
    return {s.name: value_at(s, facts, x) for s in strategies}


def _top(values):
    if any(v is None for v in values.values()):
        return None
    return max(values, key=lambda n: values[n])


def _jumped(left, right):
    for name in left:
        a, b = left[name], right[name]
        if a is None or b is None:
            return name
        if abs(a - b) > max(_ABS_JUMP, _REL_JUMP * max(abs(a), abs(b))):
            return name
    return None


def switch_points(strategies, facts, grid):
    out = {"points": [], "discontinuities": [], "undetermined": [], "excluded": [],
           "always_top": None, "error": ""}
    units = {s.model.unit for s in strategies}
    if len(strategies) < 2:
        out["error"] = "策が1つで比べられない"
        return out
    if len(units) != 1 or "" in units:
        out["error"] = "策どうしの unit が揃っていない(空を含む)"
        return out
    samples = []
    for x in grid:
        vals = _values(strategies, facts, x)
        if any(v is None for v in vals.values()):
            out["excluded"].append(x)
            continue
        samples.append((x, vals))
    if not samples:
        out["error"] = "全策の推定を計算できる点が無い"
        return out
    failing = [s.name for s in strategies if all(value_at(s, facts, x) is None for x in grid)]
    if failing:
        out["error"] = f"計算できない策がある: {failing}"
        return out
    for (x0, v0), (x1, v1) in zip(samples, samples[1:]):
        if _top(v0) == _top(v1):
            continue
        if any(x0 < e < x1 for e in out["excluded"]):
            continue  # 計算失敗点をまたぐ区間は二分しない
        lo, hi, vlo, vhi = x0, x1, v0, v1
        while abs(hi - lo) > _REL_WIDTH * max(abs(lo), abs(hi), 1e-12):
            mid = (lo + hi) / 2
            vmid = _values(strategies, facts, mid)
            if _top(vmid) is None:
                break
            if _top(vmid) == _top(vlo):
                lo, vlo = mid, vmid
            else:
                hi, vhi = mid, vmid
        if abs(hi - lo) > _REL_WIDTH * max(abs(lo), abs(hi), 1e-12):
            out["undetermined"].append((lo + hi) / 2)
        elif (name := _jumped(vlo, vhi)) is not None:
            out["discontinuities"].append({"near": (lo + hi) / 2, "strategy": name})
        else:
            out["points"].append({"at": (lo + hi) / 2, "from": _top(vlo), "to": _top(vhi)})
    if not out["points"] and not out["discontinuities"]:
        out["always_top"] = _top(samples[0][1])
    return out
```

(`always_top` は「調べた範囲の格子点では常に上」という近似の意味で返す。出力側で文言にする)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest core/tests/test_uncertainty.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/uncertainty.py core/tests/test_uncertainty.py
git commit -m "feat(core): 最上位の策が入れ替わる切り替え点を逆算する"
```

### Task 4: 候補の組・波及範囲・並べ方・add_alternative_option

**Files:**
- Modify: `core/src/medo_core/uncertainty.py`, `core/src/medo_core/status.py`
- Test: `core/tests/test_uncertainty.py`, `core/tests/test_status.py`

**Interfaces:**
- Consumes: `Hypothesis`(既存)、Task 3 の結果
- Produces:
  - `candidate_pairs(hypotheses: list[Hypothesis]) -> list[tuple[str, str]]`(向きごと、`unvalidated`/`validating` のみ、同じ `fermi_ref.artifact_id` か `challenge_ids` の共通がある組)
  - `reach(nodes: list[str], edges: list[tuple[str, str, str]]) -> dict[str, dict]`(edges は `(a, b, "determines"|"narrows")`、戻りは `{id: {"determines": int, "narrows": int}}`)
  - `rank(items: list[dict]) -> list[dict]`(spec §6.1 の順。item は `id`/`kind`/`switch`(bool)/`reach`(int | "unknown" | "not_applicable")/`swing_ratio`/`decision_relevant`/`effort`)
  - status: 現在の mini-prfaq の策が1つなら `add_alternative_option`(refs: mini-prfaq のID)

- [ ] **Step 1: Write the failing tests**

```python
def test_reach_counts_determines_only_and_collapses_cycles():
    edges = [("h1", "h2", "determines"), ("h2", "h1", "determines"),
             ("h2", "h3", "determines"), ("h1", "h4", "narrows")]
    r = reach(["h1", "h2", "h3", "h4"], edges)
    assert r["h1"]["determines"] == 2   # h2 と h3(自分は数えない)
    assert r["h1"]["narrows"] == 1 and r["h3"]["determines"] == 0


def test_rank_order():
    items = [
        {"id": "hyp-3", "kind": "hyp", "switch": False, "reach": 5, "swing_ratio": 2.0,
         "decision_relevant": 0.9, "effort": "ask"},
        {"id": "hyp-1", "kind": "hyp", "switch": True, "reach": 0, "swing_ratio": 0.1,
         "decision_relevant": None, "effort": "experiment"},
        {"id": "oq-1", "kind": "oq", "switch": False, "reach": "not_applicable",
         "swing_ratio": None, "decision_relevant": 0.9, "effort": "ask"},
        {"id": "hyp-2", "kind": "hyp", "switch": False, "reach": "unknown", "swing_ratio": None,
         "decision_relevant": None, "effort": None},
    ]
    assert [i["id"] for i in rank(items)] == ["hyp-1", "hyp-3", "oq-1", "hyp-2"]


def test_candidate_pairs_by_shared_fermi_or_challenge():
    h = [Hypothesis(id="hyp-1", kind="impact", statement="a", challenge_ids=["ch-1"]),
         Hypothesis(id="hyp-2", kind="impact", statement="b", challenge_ids=["ch-1"]),
         Hypothesis(id="hyp-3", kind="impact", statement="c", challenge_ids=["ch-9"],
                    status="validated")]
    assert set(candidate_pairs(h)) == {("hyp-1", "hyp-2"), ("hyp-2", "hyp-1")}
```

`test_status.py`: 策が1つの mini-prfaq を保存した案件で `project_status(..., view="summary")` の actions に `add_alternative_option` が含まれること(既存の status テストのヘルパーで要件と mini-prfaq を用意する)。

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest core/tests/test_uncertainty.py core/tests/test_status.py -k "reach or rank or candidate or alternative" -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`reach`: `determines` の辺で強連結成分を求め(Tarjan か Kosaraju)、縮約グラフで各節点から到達できる元の節点数(自分の成分の他の節点を含み、自分は除く)を数える。`narrows` は直接の出次数。

`rank`: 次のキーで `sorted`:

```python
_EFFORT = {"ask": 0, "research": 1, "experiment": 2}


def _key(i):
    reach = i["reach"] if isinstance(i["reach"], int) else -1
    ratio = i["swing_ratio"] if i["swing_ratio"] is not None else -1.0
    relevant = 0 if (i["decision_relevant"] or 0) >= 0.5 else 1
    effort = _EFFORT.get(i["effort"], 3)
    kind = 0 if i["kind"] == "hyp" else 1
    num = int(i["id"].rsplit("-", 1)[1])
    return (0 if i["switch"] else 1, -reach, -ratio, relevant, effort, kind, num)


def rank(items):
    return sorted(items, key=_key)
```

`candidate_pairs`: 未検証の仮説の全順序対のうち、`fermi_ref` の `artifact_id` が同じか、`challenge_ids` に共通がある組。

status: `build_actions` に、`ctx.artifacts` の現在の mini-prfaq(`_current_artifact_ids` で決まるもの)の `options` が1つなら `add("add_alternative_option", [mini_id], reason="策が1つで比べられない")`。置き場所は `regenerate_stale_artifacts` の前。

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/uncertainty.py core/src/medo_core/status.py core/tests/test_uncertainty.py core/tests/test_status.py
git commit -m "feat(core): 決め手の波及範囲と不確実性の並べ方"
```

**Part A の終わり**: PR(保存データのスキーマと status の actions が変わるので人間レビュー対象)。

---

## Part B: cli と Jev

### Task 5: jev.judge_uncertainty

**Files:**
- Modify: `cli/src/medo_cli/jev.py`
- Test: `cli/tests/test_cli.py`

**Interfaces:**
- Produces: `judge_uncertainty(items: list[dict], pairs: list[tuple[str, str]], context: dict) -> dict` を返す: `{"implies": {(a, b): {"choice": str, "confidence": float}}, "decision_relevant": {id: float}, "effort": {id: str}}`。items は `{"id", "text", "kind", "needs_relevance": bool}`。鍵なしは `JevUnavailable`、失敗は `RuntimeError`(既存の `_post` を使う)

- [ ] **Step 1: Write the failing test**

```python
def test_judge_uncertainty_asks_three_kinds(monkeypatch):
    import medo_cli.jev as jev
    sent = {}

    def fake(request, timeout):
        body = json.loads(request.data)
        sent.update(body)
        answers = {qid: ({"choice": "determines", "confidence": 0.9} if "implies" in qid
                         else {"choice": "ask", "confidence": 0.8} if "effort" in qid
                         else {"noul": 0.7}) for qid in body["questions"]}
        return _FakeResponse({"answers": answers})

    monkeypatch.setenv("TYPESAFE_API_KEY", "dummy")
    monkeypatch.setattr(jev, "urlopen", fake)
    items = [{"id": "hyp-1", "text": "a", "kind": "hyp", "needs_relevance": False},
             {"id": "oq-1", "text": "b", "kind": "oq", "needs_relevance": True}]
    out = jev.judge_uncertainty(items, [("hyp-1", "hyp-2")], {"options": []})
    assert out["implies"][("hyp-1", "hyp-2")]["choice"] == "determines"
    assert out["decision_relevant"] == {"oq-1": 0.7}
    assert out["effort"] == {"hyp-1": "ask", "oq-1": "ask"}
    assert len(sent["questions"]) == 1 + 1 + 2
```

(`_FakeResponse` は Part B の knowledge-digest で使った既存ヘルパー)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest cli/tests/test_cli.py -k judge_uncertainty -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

質問IDは `i{n}_implies`(pairs の n 番目、`choice`: `determines` / `narrows` / `none`、instructions は「`pairs[n].a` の仮説が確定すると、`pairs[n].b` の仮説も決まるか」、criteria は spec §5 の3値)、`r{n}_relevant`(`needs_relevance` の item のみ、noul、「これが解消したら、どの策を取るかが変わり得るか」)、`e{n}_effort`(全 item、choice: `ask` すぐ聞ける / `research` 調査が要る / `experiment` 実証が要る)。`state` は `{"items": items, "pairs": [{"a": a_text, "b": b_text}...], "context": context}`(pairs の本文は items から引く)。応答の欠けは `RuntimeError("Jevの応答が不正です")`。

- [ ] **Step 4: Run tests**

Run: `uv run pytest cli/tests -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cli/src/medo_cli/jev.py cli/tests/test_cli.py
git commit -m "feat(cli): 不確実性の含意・判断への効き・手間をJevで分類する"
```

### Task 6: artifacts save の新オプションと status --view uncertainty

**Files:**
- Create: `cli/src/medo_cli/commands/uncertainty.py`
- Modify: `cli/src/medo_cli/main.py`
- Test: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1〜5
- Produces:
  - `artifacts save` に `--tier "<名前>=<tier>"`(複数可)、`--option-fermi "<名前>=fermi-vN"`(複数可)、`--pivot`、`--pivot-unit`、`--pivot-var "<名前>=<変数>"`(複数可)、`--pivot-range "<下限>,<上限>"`。`--options` の解釈は変えない
  - `VIEWS` に `uncertainty`。`status --view uncertainty` は `commands/uncertainty.py` の `build_view(storage, knowledge_root, project) -> dict` を呼ぶ(core の `project_status` を経由しない。Jev を使うため)
  - 出力(json): `{"project", "judge": "ok"|"unavailable", "mini_prfaq": id|None, "strategies": [{"name","tier","value","unit","fermi"}], "pivot": {"name","unit","range","grid": "log"|"linear"}, "switch": {Task 3 の結果}, "fixed_assumptions": {strategy: {var: value}}, "stale": [...], "unverified_facts": [...], "items": [...rank 済み]}`。digest は items を1行ずつ(`<id> switch=<bool> reach=<..> ask: <問い>`)

- [ ] **Step 1: Write the failing tests**

```python
def _fermi_file(tmp_path, name, formula, x, unit="万円/年"):
    p = tmp_path / f"{name}.yaml"
    p.write_text(yaml.safe_dump({"name": name, "unit": unit, "formula": formula,
                                 "variables": {"rate": {"assume": x}, "base": {"assume": 100}}}),
                 encoding="utf-8")
    return p


def test_options_with_colon_in_approach_unchanged(medo_home, tmp_path):
    _save_requirements(tmp_path)
    content = tmp_path / "c.md"; content.write_text("x", encoding="utf-8")
    r = runner.invoke(app, ["artifacts", "save", "--project", "yoyaku", "--type", "mini-prfaq",
                            "--file", str(content), "--requirements-version", "1",
                            "--generated-by", "claude", "--options", "A:業務改革:段階導入",
                            "--tier", "A=main"])
    assert r.exit_code == 0, r.output
    a = json.loads(runner.invoke(app, ["artifacts", "get", "--project", "yoyaku", "--id",
                                       "mini-prfaq-v1", "--format", "json"]).stdout)
    assert a["options"][0]["approach_type"] == "業務改革:段階導入" and a["options"][0]["tier"] == "main"


def test_view_without_pivot_reports_reason(medo_home, tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    _save_requirements(tmp_path)
    content = tmp_path / "c.md"; content.write_text("x", encoding="utf-8")
    runner.invoke(app, ["artifacts", "save", "--project", "yoyaku", "--type", "mini-prfaq",
                        "--file", str(content), "--requirements-version", "1",
                        "--generated-by", "claude", "--options", "A:x,B:y"])
    out = json.loads(runner.invoke(app, ["status", "--project", "yoyaku", "--view",
                                         "uncertainty"]).stdout)
    assert out["judge"] == "unavailable" and out["switch"]["error"]


def test_view_computes_switch_point(medo_home, tmp_path, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    _save_requirements(tmp_path)
    for name, formula in (("matsu", "rate * base * 3 - 120"), ("take", "rate * base * 2 - 60")):
        runner.invoke(app, ["fermi", "calc", "--project", "yoyaku",
                            "--file", str(_fermi_file(tmp_path, name, formula, 0.5))])
    content = tmp_path / "c.md"; content.write_text("x", encoding="utf-8")
    r = runner.invoke(app, ["artifacts", "save", "--project", "yoyaku", "--type", "mini-prfaq",
                            "--file", str(content), "--requirements-version", "1",
                            "--generated-by", "claude", "--options", "松案:x,竹案:y",
                            "--tier", "松案=matsu", "--tier", "竹案=take",
                            "--option-fermi", "松案=fermi-v1", "--option-fermi", "竹案=fermi-v2",
                            "--pivot", "利用率", "--pivot-unit", "比率",
                            "--pivot-var", "松案=rate", "--pivot-var", "竹案=rate",
                            "--pivot-range", "0,1"])
    assert r.exit_code == 0, r.output
    out = json.loads(runner.invoke(app, ["status", "--project", "yoyaku", "--view",
                                         "uncertainty"]).stdout)
    points = out["switch"]["points"]
    assert len(points) == 1 and points[0]["at"] == pytest.approx(0.6, rel=1e-2)
    assert (points[0]["from"], points[0]["to"]) == ("竹案", "松案")


def test_view_jev_failure_exits_nonzero(medo_home, tmp_path, monkeypatch):
    from medo_cli.commands import uncertainty as u
    _save_requirements(tmp_path)
    monkeypatch.setenv("TYPESAFE_API_KEY", "dummy")
    monkeypatch.setattr(u, "judge_uncertainty",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("HTTP 500")))
    r = runner.invoke(app, ["status", "--project", "yoyaku", "--view", "uncertainty"])
    assert r.exit_code != 0 and "error:" in r.output
```

(要件の fixture `_save_requirements` は既存。`fermi calc` が `unit` を保存済みモデルに残すこと、`--requirements-version` の要否は既存の `artifacts save` テストに合わせる。仮説を含む要件で `items` が rank 順に並ぶテストも1件足す: 仮説2件(同じ課題)+ Jev を偽物にして `determines` を返させ、`reach` が 1 になること)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest cli/tests/test_cli.py -k "options_with_colon or view_" -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

`artifacts save`: 新オプションを `dict(v.split("=", 1) for v in tier)` のように読み、`--options` から作った `option_metas` に名前で当てる。`--options` に無い名前、`=` の無い値、同じ名前への重複指定は `_fail`。`--pivot-range` は `float` 2つ。

`commands/uncertainty.py` の `build_view`:
1. `ArtifactStore._load_all` と `_current_artifact_ids` で現在の mini-prfaq を選ぶ(無ければ `items` だけ返し `mini_prfaq: None`)
2. 策ごとに `fermi` 生成物を読み、`content` の `model` を `FermiModel` で検証(失敗は `strategies[i]["error"]` に理由)。`pivot_variable` がモデルに無いか `assume` でなければエラー
3. 全策が有効で `pivot` があれば `search_grid`(策の仮定値と `pivot_range`)→ `sensitivity` → `switch_points`。今のファクト(`FactStore.list`)で計算し、`evaluate` の `unverified_facts` / `doubtful_facts` を集める。fermi・mini-prfaq の stale は `freshness`(既存)から
4. 要件の仮説と未確定事項から items を作り、`candidate_pairs`、Jev(`judge_uncertainty`。`JevUnavailable` なら `judge: unavailable` で Jev 由来の値を null/`unknown`)、`reach`、`rank`
5. `ask` の文言: 切り替え点に結びつく仮説には「他の仮定が今のままなら、<pivot> は <at> 以上か」(複数の点があれば各点)

`status` コマンド: `view == "uncertainty"` のとき `build_view` を呼び、`RuntimeError` は `_fail`。digest 出力は `_echo_uncertainty_digest`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cli/src/medo_cli/commands/uncertainty.py cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(cli): status --view uncertainty と策のオプション"
```

### Task 7: implies の評価セット

**Files:**
- Create: `scripts/eval/implies_cases.json`, `scripts/eval/run_implies_eval.py`

- [ ] **Step 1: 評価セットを作る**

`[{"split": "tune"|"validate", "a": "<仮説の本文>", "b": "<仮説の本文>", "context": {...}, "label": "determines"|"narrows"|"none"}]`。各 split に各ラベル4組以上。必須: 前提の仮説(「顧客は月次で発注している」)とそれに依存する仮説(「月次の需要予測で欠品が減る」)の determines、同じ課題の独立した2仮説の none、範囲を狭めるだけの narrows。ラベルは Jev に渡さない。

- [ ] **Step 2: 評価スクリプトを書く**

```python
"""正解付きの組で implies の判定を評価し、閾値を決める。"""

import json
import sys
from pathlib import Path

from medo_cli.jev import judge_uncertainty

CASES = Path(__file__).with_name("implies_cases.json")


def _judge(cases):
    items, pairs = [], []
    for n, c in enumerate(cases):
        a, b = f"hyp-{2 * n + 1}", f"hyp-{2 * n + 2}"
        items += [{"id": a, "text": c["a"], "kind": "hyp", "needs_relevance": False},
                  {"id": b, "text": c["b"], "kind": "hyp", "needs_relevance": False}]
        pairs.append((a, b))
    out = judge_uncertainty(items, pairs, {})
    return [out["implies"][p] for p in pairs]


def _edge(j, t):
    return j["choice"] if j["choice"] in ("determines", "narrows") and j["confidence"] >= t else "none"


def main() -> int:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    tune = [c for c in cases if c["split"] == "tune"]
    val = [c for c in cases if c["split"] == "validate"]
    tj = _judge(tune)
    chosen = None
    for t in [x / 100 for x in range(50, 100, 5)]:
        false_edges = sum(1 for c, j in zip(tune, tj) if c["label"] == "none" and _edge(j, t) != "none")
        if false_edges / max(1, sum(c["label"] == "none" for c in tune)) <= 0.1:
            chosen = t
            break
    if chosen is None:
        print("error: 調整用の組で誤って辺を張る率を1割以下にできる閾値がありません", file=sys.stderr)
        return 1
    vj = _judge(val)
    nones = [(c, j) for c, j in zip(val, vj) if c["label"] == "none"]
    dets = [(c, j) for c, j in zip(val, vj) if c["label"] == "determines"]
    false_rate = sum(_edge(j, chosen) != "none" for _, j in nones) / max(1, len(nones))
    det_rate = sum(_edge(j, chosen) == "determines" for _, j in dets) / max(1, len(dets))
    print(f"threshold={chosen} false_edge_rate={false_rate:.2f} determines_recall={det_rate:.2f}")
    ok = false_rate <= 0.1 and det_rate >= 0.8
    print("accept" if ok else "reject")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 実行する**

Run: `python3 scripts/eval/run_implies_eval.py`
Expected: accept。満たさなければ Jev の instructions/criteria を最大3回調整(評価セットは変えない)。閾値が 0.8 から変われば `commands/uncertainty.py` の既定値と spec §5 を合わせ、tune で閾値を識別できなかった場合はその旨を評価記録に残す(knowledge-digest と同じ扱い)

- [ ] **Step 4: Commit**

```bash
git add scripts/eval/implies_cases.json scripts/eval/run_implies_eval.py
git commit -m "test(scripts): implies の評価セットと閾値"
```

**Part B の終わり**: PR(CLIの新オプションとビューで人間レビュー対象)。

---

## Part C: Skill と同期

### Task 8: propose-options / decide と steering

**Files:**
- Modify: `skills/src/medo-propose-options/SKILL.md`, `skills/src/medo-decide/SKILL.md`, `skills/tests/test_build.py`, `docs/usage.md`, `.claude/steering/structure.md`

- [ ] **Step 1: Write the failing test**

```python
def test_propose_options_creates_two_to_three_strategies_with_pivot(tmp_path):
    text = _built(tmp_path, "medo-propose-options")
    assert "--tier" in text and "--option-fermi" in text and "--pivot-var" in text
    assert "2〜3" in text or "最低2つ" in text


def test_decide_reads_uncertainty_view(tmp_path):
    assert "--view uncertainty" in _built(tmp_path, "medo-decide")
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest skills/tests -k "pivot or uncertainty" -v`
Expected: FAIL

- [ ] **Step 3: Skill を更新する**

`medo-propose-options` の候補セット保存の手順に追記(行数に余裕あり):
- 策は**最低2つ・最大3つ**。メインとサブ(`--tier <名前>=main|sub`)、3つなら松竹梅(`matsu|take|ume`)
- 策ごとに `medo fermi calc` で推定を作り(`unit` を付け、仮定には根拠のメモ)、`--option-fermi <名前>=fermi-vN` で結ぶ
- 策を分けるパラメタを `--pivot <名前> --pivot-unit <単位> --pivot-var <策>=<変数>` で明示する。**対応する変数はすべての策で同じ単位・尺度で書く**。意味のある範囲があれば `--pivot-range <下限>,<上限>`

`medo-decide`(80行上限、既存行に組み込む): 振り返りで `medo status --project <id> --view uncertainty` を読み、最上位の `ask` を返答の中で示して次の焦点にするかを尋ねる。最上位が `oq-N` なら、まず仮説にして要件に保存してから焦点にする。

- [ ] **Step 4: 同期**

- `structure.md` §2 に `uncertainty.py` を1行、§3 に `commands/uncertainty.py`
- `docs/usage.md` の status の節に `--view uncertainty` の例

- [ ] **Step 5: Run and commit**

Run: `uv run pytest -q && python3 skills/build.py`
Expected: PASS(decide は80行以内)

```bash
git add skills .claude/steering/structure.md docs/usage.md
git commit -m "feat(skills): 策を2〜3つ作り、次に潰す不確実性を焦点の候補にする"
```

**Part C の終わり**: PR(Skill契約で人間レビュー対象)。
