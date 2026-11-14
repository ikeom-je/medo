"""現在の要件とファクトから、不確実性のビューを組み立てる。"""

import json
import math
from datetime import date
from pathlib import Path

from medo_cli.jev import JevUnavailable, judge_uncertainty
from medo_core.artifacts import Artifact, ArtifactStore, OptionMeta
from medo_core.context import _current_artifact_ids, make_citation_checker
from medo_core.facts import Fact, FactStore
from medo_core.fermi import FermiModel, evaluate
from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.storage import Storage
from medo_core.uncertainty import Strategy, candidate_pairs, rank, reach, search_grid, sensitivity, switch_points

IMPLIES_THRESHOLD = 0.5


def _error(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def _load_strategy(option: OptionMeta, artifacts: dict[str, Artifact], facts: dict[str, Fact],
                   pivot: str) -> tuple[dict, Strategy | None]:
    summary = {"name": option.name, "tier": option.tier, "fermi": option.fermi,
               "value": None, "unit": ""}
    model = None
    if not option.fermi:
        error = _error("missing_fermi", "策に fermi が無い")
    elif option.fermi not in artifacts:
        error = _error("missing_artifact", f"fermi の参照先が無い: {option.fermi}")
    elif artifacts[option.fermi].type != "fermi":
        error = _error("invalid_artifact_type", f"参照先が fermi ではない: {option.fermi}")
    else:
        try:
            content = json.loads(artifacts[option.fermi].content)
            model = FermiModel.model_validate(content["model"])
        except (KeyError, TypeError, ValueError) as exc:
            error = _error("invalid_model", f"fermi のモデルを読めない: {exc}")
        else:
            summary["unit"] = model.unit
            summary["fixed_assumptions"] = {
                name: var.assume for name, var in model.variables.items()
                if var.assume is not None and (not pivot or name != option.pivot_variable)
            }
            summary["cited_facts"] = sorted({v.fact for v in model.variables.values() if v.fact})
            try:
                result = evaluate(model, facts)
                if not math.isfinite(result.value):
                    raise ValueError("推定値が有限ではない")
                summary["value"] = result.value
                summary["unverified_facts"] = result.unverified_facts
                summary["doubtful_facts"] = result.doubtful_facts
            except (ValueError, ZeroDivisionError, OverflowError, SyntaxError, TypeError) as exc:
                error = _error("calculation_failed", f"基準の推定を計算できない: {exc}")
            else:
                variable = model.variables.get(option.pivot_variable)
                if pivot and (variable is None or variable.assume is None):
                    error = _error("invalid_pivot_variable", "pivot_variable が無いか assume ではない")
                else:
                    return summary, Strategy(name=option.name, tier=option.tier, model=model,
                                             variable=option.pivot_variable)
    summary["error"] = error
    return summary, None


def _comparison(mini: Artifact | None, summaries: list[dict], strategies: list[Strategy],
                facts: dict[str, Fact]) -> tuple[dict, list[float], dict]:
    result = {"points": [], "discontinuities": [], "undetermined": [], "excluded": [],
              "always_top": None, "error": ""}
    if mini is None or not summaries:
        result["error"] = "打ち手の候補が無い"
    elif len(summaries) == 1:
        result["error"] = "策が1つで比べられない"
    elif not mini.pivot:
        result["error"] = "pivot が無い"
    elif any(s.get("error") for s in summaries):
        result["error"] = "計算できない策があるため、全策の比較は計算しない"
    else:
        try:
            grid = search_grid([s.model.variables[s.variable].assume for s in strategies],
                               mini.pivot_range)
        except ValueError as exc:
            result["error"] = str(exc)
        else:
            swings = {s.name: sensitivity(s, facts, grid) for s in strategies}
            return switch_points(strategies, facts, grid), grid, swings
    return result, [], {}


def _items(doc: RequirementsDoc, mini: Artifact | None, switch: dict, swings: dict,
           summaries: list[dict]) -> list[dict]:
    items = []
    for hypothesis in doc.hypotheses:
        if hypothesis.status not in ("unvalidated", "validating"):
            continue
        linked = [o for o in mini.options if hypothesis.fermi_ref
                  and o.fermi == hypothesis.fermi_ref.artifact_id
                  and o.pivot_variable == hypothesis.fermi_ref.variable_name] if mini else []
        valid_switch = bool(linked and switch["points"])
        linked_swings = [swings[o.name] for o in linked if o.name in swings]
        ratios = [s["ratio"] for s in linked_swings if s["ratio"] is not None]
        asks = [f"他の仮定が今のままなら、{mini.pivot} は {point['at']:.6g} 以上か"
                for point in switch["points"]] if valid_switch else [hypothesis.statement]
        errors = [s["error"] for s in summaries if s.get("error") and hypothesis.fermi_ref
                  and s["fermi"] == hypothesis.fermi_ref.artifact_id]
        if linked and switch["error"]:
            errors.append(_error("comparison_unavailable", switch["error"]))
        items.append({"id": hypothesis.id, "kind": "hyp", "text": hypothesis.statement,
                      "challenge_ids": hypothesis.challenge_ids,
                      "validation_method": hypothesis.validation_method,
                      "switch": valid_switch, "pivot": valid_switch,
                      "swing": max((s["swing"] for s in linked_swings), default=None),
                      "swing_ratio": max(ratios, default=None), "ask": " / ".join(asks),
                      "errors": errors, "needs_relevance": not valid_switch})
    for question in doc.open_questions:
        items.append({"id": question.id, "kind": "oq", "text": question.text,
                      "switch": False, "pivot": False, "swing": None, "swing_ratio": None,
                      "ask": question.text, "errors": [], "needs_relevance": True})
    return items


def _classify(items: list[dict], doc: RequirementsDoc, mini: Artifact | None) -> str:
    context = {"challenges": [{"id": c.id, "text": c.text} for c in doc.challenges],
               "options": [{"name": o.name, "tier": o.tier} for o in mini.options] if mini else []}
    try:
        judgment_items = [
            {key: item[key] for key in ("id", "text", "kind", "needs_relevance",
                                       "challenge_ids", "validation_method") if key in item}
            for item in items
        ]
        judgments = judge_uncertainty(judgment_items, candidate_pairs(doc.hypotheses), context)
    except JevUnavailable:
        judgments = None
    edges = []
    evidence = []
    if judgments is not None:
        for (a, b), judgment in judgments["implies"].items():
            if judgment["choice"] in ("determines", "narrows") and judgment["confidence"] >= IMPLIES_THRESHOLD:
                edges.append((a, b, judgment["choice"]))
                evidence.append({"from": a, "to": b, **judgment})
    counts = reach([i["id"] for i in items if i["kind"] == "hyp"], edges)
    for item in items:
        item_id = item["id"]
        if item["kind"] == "oq":
            item["reach"] = "not_applicable"
            narrows = None
        elif judgments is None:
            item["reach"] = "unknown"
            narrows = None
        else:
            item["reach"] = counts[item_id]["determines"]
            narrows = counts[item_id]["narrows"]
        item["keystone"] = {"reach": item["reach"], "narrows": narrows,
                            "edges": [e for e in evidence if e["from"] == item_id]}
        item["decision_relevant"] = judgments["decision_relevant"].get(item_id) if judgments else None
        item["effort"] = judgments["effort"].get(item_id) if judgments else None
    return "ok" if judgments is not None else "unavailable"


def build_view(storage: Storage, knowledge_root: Path, project: str) -> dict:
    """現在版の候補を比較し、仮説と未確定事項を優先順で返す。"""
    doc = RequirementsStore(storage).get(project)
    if doc is None:
        raise ValueError(f"プロジェクトが存在しません: {project}")
    store = ArtifactStore(storage)
    artifacts = store._load_all(project)
    mini_id = _current_artifact_ids(artifacts).get("mini-prfaq")
    mini = artifacts.get(mini_id)
    facts = {f.fact_id: f for f in FactStore(storage).list(project)}
    summaries, strategies = [], []
    for option in mini.options if mini else []:
        summary, strategy = _load_strategy(option, artifacts, facts, mini.pivot)
        summaries.append(summary)
        if strategy is not None:
            strategies.append(strategy)
    switch, grid, swings = _comparison(mini, summaries, strategies, facts)
    items = _items(doc, mini, switch, swings, summaries)
    judge = _classify(items, doc, mini)
    used_ids = {mini_id} | {o.fermi for o in mini.options} if mini else set()
    freshness = store.freshness(
        project, doc.version, {c.id for c in doc.challenges if c.scope == "core"},
        is_citation_stale=make_citation_checker(storage, project, knowledge_root), today=date.today(),
    )
    used_freshness = {a_id: freshness[a_id].model_dump(mode="json")
                      for a_id in sorted(used_ids) if a_id in freshness}
    cited = set(mini.cited_facts) if mini else set()
    for summary in summaries:
        cited.update(summary.get("cited_facts", []))
    referenced = [facts[f_id] for f_id in sorted(cited) if f_id in facts]
    return {
        "project": project, "judge": judge, "mini_prfaq": mini_id,
        "strategies": summaries,
        "pivot": {"name": mini.pivot if mini else "", "unit": mini.pivot_unit if mini else "",
                  "range": [grid[0], grid[-1]] if grid else None,
                  "grid": ("log" if grid[0] > 0 else "linear") if grid else None},
        "switch": switch, "approximate": True,
        "fixed_assumptions": {s["name"]: s.get("fixed_assumptions", {}) for s in summaries},
        "freshness": used_freshness,
        "stale": [a_id for a_id, state in used_freshness.items() if state["state"] == "stale"],
        "unverified_facts": [f.fact_id for f in referenced
                             if f.verification.status in ("unverified", "legacy")],
        "doubtful_facts": [f.fact_id for f in referenced if f.verification.status == "verified"
                           and f.verification.support == "doubtful"],
        "items": rank(items),
    }
