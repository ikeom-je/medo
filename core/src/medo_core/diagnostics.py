"""案件内容の充足診断。

診断は報告であって強制ではない。未接続を検出しても保存は拒否しない。
"""

from medo_core.artifacts import Freshness
from medo_core.checks import CheckState, checks_for_phase
from medo_core.requirements import RequirementsDoc
from medo_core.responses import ConvergenceTarget

SCOPED_SECTIONS = (
    "as_is", "to_be", "gaps", "bottlenecks", "challenges", "constraints", "open_questions"
)

# 判断できないまま進むと提案の土台が崩れるため、保留を許さず昇格のみで先へ進める。
NO_DEFER_CHECKS = ("reality_gap", "decision_maker")


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


def phase_readiness(
    readiness_state: str,
    artifacts: dict,
    freshness: dict,
    responses: list,
    target: ConvergenceTarget,
    decision_makers: set[str],
) -> dict:
    """フェーズ完了ゲート。最終提案スライドを提示した後に評価する。

    「何を見て承認したか」を一意に決めるため、現在の最終提案スライドへの
    signoff だけを有効とする(fold_responses が現在対象で畳み込む)。
    承認者は決裁者に限る。頭数では判定しない。
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
        r.purpose == "phase_signoff" and r.reaction == "agreed"
        and not r.expired and r.on_current_target
        and r.stakeholder_id in decision_makers
        for r in responses
    ):
        failed.append({"code": "phase_signoff_missing", "refs": sorted(decision_makers)})

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
