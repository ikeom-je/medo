"""次に潰すべき不確実性の決定論部分。Jevの判定は呼び出し側から受け取る。"""

from __future__ import annotations

import math

from pydantic import BaseModel

from medo_core.facts import Fact
from medo_core.fermi import FermiModel, FermiVar, evaluate
from medo_core.nodes import Hypothesis


class Strategy(BaseModel):
    name: str
    tier: str = ""
    model: FermiModel
    variable: str


def _log(lo: float, hi: float, n: int) -> list[float]:
    start, stop = math.log(lo), math.log(hi)
    return [lo, *[math.exp(start + (stop - start) * i / (n - 1))
                  for i in range(1, n - 1)], hi]


def _lin(lo: float, hi: float, n: int) -> list[float]:
    return [lo, *[lo * (1 - i / (n - 1)) + hi * i / (n - 1)
                  for i in range(1, n - 1)], hi]


def search_grid(
    assumed: list[float], explicit: tuple[float, float] | None, points: int = 200,
) -> list[float]:
    if points < 2:
        raise ValueError("探索には2点以上が必要です")
    if explicit is not None:
        lo, hi = explicit
    else:
        if not assumed or not all(math.isfinite(value) for value in assumed):
            raise ValueError("探索範囲には有限の仮定値が必要です")
        lo, hi = min(assumed), max(assumed)
        if lo > 0:
            lo, hi = lo / 10, hi * 10
        else:
            span = (hi - lo) or max(abs(lo), abs(hi)) or 1.0
            lo, hi = lo - span, hi + span
    if not (math.isfinite(lo) and math.isfinite(hi) and lo < hi):
        raise ValueError("探索範囲は有限で 下限 < 上限 である必要があります")
    return _log(lo, hi, points) if lo > 0 else _lin(lo, hi, points)


def value_at(s: Strategy, facts: dict[str, Fact], x: float) -> float | None:
    variable = s.model.variables.get(s.variable)
    if variable is None or variable.assume is None:
        return None
    variables = {**s.model.variables, s.variable: FermiVar(assume=x)}
    try:
        value = evaluate(s.model.model_copy(update={"variables": variables}), facts).value
        return value if math.isfinite(value) else None
    except (ValueError, ZeroDivisionError, OverflowError, SyntaxError, TypeError):
        return None


def sensitivity(s: Strategy, facts: dict[str, Fact], grid: list[float]) -> dict:
    variable = s.model.variables.get(s.variable)
    base = value_at(s, facts, variable.assume) if variable and variable.assume is not None else None
    values = [v for x in grid if (v := value_at(s, facts, x)) is not None]
    swing = (max(values) - min(values)) if values else 0.0
    ratio = None if not base else swing / abs(base)
    return {"swing": swing, "ratio": ratio, "base": base}


_ABS_JUMP = 1e-9
_REL_JUMP = 1e-2
_REL_WIDTH = 1e-3


def _values(strategies: list[Strategy], facts: dict[str, Fact], x: float) -> dict:
    return {s.name: value_at(s, facts, x) for s in strategies}


def _top(values: dict) -> str | None:
    if not values or any(v is None for v in values.values()):
        return None
    return max(values, key=lambda name: values[name])


def _jumped(left: dict, right: dict) -> str | None:
    for name in left:
        a, b = left[name], right[name]
        if abs(a - b) > max(_ABS_JUMP, _REL_JUMP * max(abs(a), abs(b))):
            return name
    return None


def _refine_switch(strategies, facts, lo, hi, vlo, vhi) -> tuple[str, dict | float]:
    while abs(hi - lo) > _REL_WIDTH * max(abs(lo), abs(hi), 1e-12):
        mid = lo / 2 + hi / 2
        if mid == lo or mid == hi:
            return "undetermined", mid
        vmid = _values(strategies, facts, mid)
        if _top(vmid) is None:
            return "undetermined", mid
        if _top(vmid) == _top(vlo):
            lo, vlo = mid, vmid
        else:
            hi, vhi = mid, vmid
    mid = lo / 2 + hi / 2
    if (name := _jumped(vlo, vhi)) is not None:
        return "discontinuities", {"near": mid, "strategy": name}
    return "points", {"at": mid, "from": _top(vlo), "to": _top(vhi)}


def switch_points(
    strategies: list[Strategy], facts: dict[str, Fact], grid: list[float],
) -> dict:
    out = {"points": [], "discontinuities": [], "undetermined": [], "excluded": [],
           "always_top": None, "error": ""}
    if len(strategies) < 2:
        out["error"] = "策が1つで比べられない" if strategies else "打ち手の候補が無い"
        return out
    if len({s.name for s in strategies}) != len(strategies):
        out["error"] = "策の名前は一意である必要があります"
        return out
    units = {s.model.unit for s in strategies}
    if len(units) != 1 or "" in units:
        out["error"] = "策どうしの unit が揃っていない(空を含む)"
        return out
    samples = [(x, _values(strategies, facts, x)) for x in grid]
    out["excluded"] = [x for x, values in samples if _top(values) is None]
    valid = [(x, values) for x, values in samples if _top(values) is not None]
    if not valid:
        out["error"] = "全策の推定を計算できる点が無い"
        return out
    failing = [s.name for s in strategies if sensitivity(s, facts, [])['base'] is None]
    if failing:
        out["error"] = f"基準の推定を計算できない策がある: {failing}"
        return out
    for (x0, v0), (x1, v1) in zip(samples, samples[1:]):
        if _top(v0) is None or _top(v1) is None or _top(v0) == _top(v1):
            continue
        result, value = _refine_switch(strategies, facts, x0, x1, v0, v1)
        out[result].append(value)
    for (x0, v0), (x1, v1) in zip(valid, valid[1:]):
        gap = [x for x in out["excluded"] if x0 < x < x1]
        # 計算できない点を挟んだ入れ替わりは二分できないが、黙って落とすと見えなくなる
        if gap and _top(v0) != _top(v1):
            out["undetermined"].append((x0 + x1) / 2)
    tops = {_top(values) for _, values in valid}
    if len(tops) == 1 and not out["discontinuities"] and not out["undetermined"]:
        out["always_top"] = _top(valid[0][1])
    return out


def candidate_pairs(hypotheses: list[Hypothesis]) -> list[tuple[str, str]]:
    active = [h for h in hypotheses if h.status in ("unvalidated", "validating")]
    return [
        (a.id, b.id)
        for a in active
        for b in active
        if a.id != b.id and (
            bool(set(a.challenge_ids) & set(b.challenge_ids))
            or (a.fermi_ref is not None and b.fermi_ref is not None
                and a.fermi_ref.artifact_id == b.fermi_ref.artifact_id)
        )
    ]


def _components(graph: dict[str, set[str]]) -> list[set[str]]:
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    stacked: set[str] = set()
    components: list[set[str]] = []

    def visit(node: str) -> None:
        indices[node] = low[node] = len(indices)
        stack.append(node)
        stacked.add(node)
        for child in sorted(graph[node]):
            if child not in indices:
                visit(child)
                low[node] = min(low[node], low[child])
            elif child in stacked:
                low[node] = min(low[node], indices[child])
        if low[node] == indices[node]:
            component: set[str] = set()
            while True:
                member = stack.pop()
                stacked.remove(member)
                component.add(member)
                if member == node:
                    break
            components.append(component)

    for node in graph:
        if node not in indices:
            visit(node)
    return components


def reach(nodes: list[str], edges: list[tuple[str, str, str]]) -> dict[str, dict]:
    graph = {node: set() for node in nodes}
    narrows = {node: set() for node in nodes}
    for source, target, relation in edges:
        if source not in graph or target not in graph:
            continue
        if relation == "determines":
            graph[source].add(target)
        elif relation == "narrows":
            narrows[source].add(target)
    components = _components(graph)
    membership = {node: i for i, component in enumerate(components) for node in component}
    condensed = {i: set() for i in range(len(components))}
    for source, children in graph.items():
        for target in children:
            a, b = membership[source], membership[target]
            if a != b:
                condensed[a].add(b)
    counts: dict[int, int] = {}
    for component in condensed:
        visited: set[int] = set()
        pending = [component]
        while pending:
            current = pending.pop()
            if current not in visited:
                visited.add(current)
                pending.extend(condensed[current] - visited)
        counts[component] = sum(len(components[i]) for i in visited) - 1
    return {node: {"determines": counts[membership[node]], "narrows": len(narrows[node])}
            for node in nodes}


_EFFORT = {"ask": 0, "research": 1, "experiment": 2}


def _rank_key(item: dict) -> tuple:
    known_reach = item["reach"] if isinstance(item["reach"], int) else -1
    ratio = item["swing_ratio"] if item["swing_ratio"] is not None else -1.0
    relevant = 0 if (item["decision_relevant"] or 0) >= 0.5 else 1
    effort = _EFFORT.get(item["effort"], 3)
    kind = 0 if item["kind"] == "hyp" else 1
    number = int(item["id"].rsplit("-", 1)[1])
    return (0 if item["switch"] else 1, -known_reach, -ratio, relevant, effort, kind, number)


def rank(items: list[dict]) -> list[dict]:
    return sorted(items, key=_rank_key)
