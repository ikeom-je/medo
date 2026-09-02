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
