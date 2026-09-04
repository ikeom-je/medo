"""プロジェクトの現在地レポート。保存状態から決定論的に導出し、LLMを挟まない。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from medo_core.checks import CHECK_REGISTRY
from medo_core.context import StatusContext, _current_artifact_ids, collect, workflow_branch
from medo_core.diagnostics import model_diagnostics, phase_readiness, readiness
from medo_core.facts import FactStore
from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.storage import Storage


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

    ctx = collect(
        storage,
        project_id,
        include_scope=include_scope,
        today=today,
        knowledge_root=knowledge_root,
    )
    model = model_diagnostics(ctx.doc, ctx.artifacts, ctx.freshness, include_scope)
    workflow = workflow_branch(ctx)
    ready = readiness(
        ctx.doc,
        ctx.target,
        ctx.checks,
        ctx.responses,
        ctx.open_review_findings,
        include_scope,
    )
    actions = build_actions(ctx, model, ready)

    branches = {
        "model": model,
        "workflow": workflow,
        "readiness": ready,
        "actions": actions,
    }
    head = {"project": project_id, "diagnostic_phase": ctx.phase}
    if view in branches:
        return {**head, view: branches[view]}
    compat = _phase1_fields(storage, ctx, today)
    if view == "full":
        decision_makers = {
            stakeholder.id
            for stakeholder in ctx.doc.stakeholders
            if stakeholder.is_decision_maker
        }
        return {
            **head,
            **branches,
            "phase_readiness": phase_readiness(
                ready["state"],
                ctx.artifacts,
                ctx.freshness,
                ctx.responses,
                ctx.target,
                decision_makers,
            ),
            **compat,
        }
    return _summary(project_id, ctx, workflow, ready, actions, compat)


def _summary(
    project_id: str,
    ctx: StatusContext,
    workflow: dict,
    ready: dict,
    actions: list[dict],
    compat: dict,
) -> dict:
    """Skillの通常利用向けに、次の行動と進行要点を返す。"""
    return {
        "actions": actions,
        "project": project_id,
        "diagnostic_phase": ctx.phase,
        "workflow": {
            "loop": {
                "round_delta": workflow["loop"]["round_delta"],
                "checkpoint": workflow["loop"]["checkpoint"],
            },
            "responses": {
                "open_objections": workflow["responses"]["open_objections"],
            },
            "review": {
                "open_findings": workflow["review"]["open_findings"],
            },
        },
        "readiness": {"state": ready["state"]},
        **compat,
    }


def _empty_status(project_id: str) -> dict:
    """要件が無い案件にフェーズ1互換の初期状態を返す。"""
    return {
        "project": project_id,
        "requirements": None,
        "facts": {"count": 0, "stale": 0},
        "artifacts": [],
        "next_step": "hearing",
    }


def _phase1_fields(
    storage: Storage,
    ctx: StatusContext,
    today: date | None,
) -> dict:
    """フェーズ1のstatusフィールドとnext_stepを従来どおり算出する。"""
    req_store = RequirementsStore(storage)
    version = req_store.latest_version(ctx.project_id)
    doc = req_store.get(ctx.project_id)
    assert doc is not None
    counts = {"confirmed": 0, "assumed": 0, "open": 0}
    for item in [*doc.functional, *doc.principles, *doc.challenges]:
        counts[item.confidence] += 1

    facts = FactStore(storage).list(ctx.project_id)

    current_artifacts = [
        (artifact_id, ctx.artifacts[artifact_id])
        for artifact_id in _current_artifact_ids(ctx.artifacts).values()
    ]
    artifact_rows = [
        {
            "id": artifact_id,
            "type": artifact.type,
            "requirements_version": artifact.requirements_version,
            "stale": ctx.freshness[artifact_id].state == "stale",
        }
        for artifact_id, artifact in sorted(current_artifacts, key=lambda item: item[1].type)
    ]

    types = {row["type"] for row in artifact_rows}
    if any(row["stale"] for row in artifact_rows):
        next_step = "regenerate-stale-artifacts"
    elif "mini-prfaq" not in types:
        next_step = "propose-options"
    elif "prfaq" not in types:
        next_step = "grow-prfaq"
    else:
        next_step = "up-to-date"

    return {
        "requirements": {
            "version": version,
            "confidence_counts": counts,
            "open_questions": len(doc.open_questions),
        },
        "facts": {
            "count": len(facts),
            "stale": sum(1 for f in facts if f.is_stale(today=today)),
        },
        "artifacts": artifact_rows,
        "next_step": next_step,
    }


def build_actions(ctx: StatusContext, model: dict, ready: dict) -> list[dict]:
    """次にできることを優先順に並べる。必ず1件以上返す。"""
    failed = {
        condition["code"]: condition["refs"]
        for condition in ready["failed_conditions"]
    }
    readiness_actions = {
        action["code"]: action for action in _readiness_driven_actions(ready)
    }
    stale = sorted(
        artifact_id
        for artifact_id in _current_artifact_ids(ctx.artifacts).values()
        if ctx.freshness[artifact_id].state == "stale"
    )
    loop_in_progress = (
        bool(ctx.pending_milestones)
        or model["structure"]["to_be"]["confirmed"] == 0
    )

    actions: list[dict] = []

    def add(code: str, refs: list[str] | None = None, **extra) -> None:
        actions.append({"code": code, **({"refs": refs} if refs else {}), **extra})

    if ctx.pending_milestones:
        add("answer_tobe_checkpoint", ctx.pending_milestones, reason="節目で未回答")
    if objections := [
        response.event_id
        for response in ctx.responses
        if response.reaction == "objected" and not response.subsumed_by
    ]:
        add("resolve_objection", sorted(objections))
    if ctx.open_review_findings:
        add("address_review_findings", ctx.open_review_findings)
    if not ctx.doc.to_be and any(item.visibility == "internal" for item in ctx.doc.as_is):
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
    if action := readiness_actions.get("elicit_internal_as_is"):
        add(action["code"], action.get("refs"))
    if action := readiness_actions.get("ground_confirmed_to_be"):
        add(action["code"], action.get("refs"))
    if _needs_discussion_slides(ctx):
        add("generate_discussion_slides")
    if action := readiness_actions.get("request_to_be_go_ahead"):
        add(action["code"], action.get("refs"))
    if stale and loop_in_progress:
        add("regenerate_stale_artifacts", stale)
    if ready["state"] == "ready":
        add("proceed_to_propose_options")
    if not actions:
        add("continue_hearing")
    return actions


def _runnable_checks(ctx: StatusContext) -> list[str]:
    """未確認で、現在の対象が存在するcheckを返す。"""
    current_artifact_ids = _current_artifact_ids(ctx.artifacts)
    return sorted(
        name
        for name, state in ctx.checks.items()
        if state.state == "unverified"
        and (
            CHECK_REGISTRY[name].binding != "artifact_bound"
            or CHECK_REGISTRY[name].target_type in current_artifact_ids
        )
    )


def _unpromoted_conflicts(doc: RequirementsDoc) -> list[str]:
    """課題へ昇格していない内部矛盾のGap IDを返す。"""
    promoted = {
        challenge.promoted_from.ref
        for challenge in doc.challenges
        if challenge.promoted_from is not None
    }
    return sorted(
        gap.id
        for gap in doc.gaps
        if gap.kind == "internal_conflict" and gap.id not in promoted
    )


def _needs_discussion_slides(ctx: StatusContext) -> bool:
    """最新のAsIsレポートに対応する討議用スライドが必要かを返す。"""
    latest_report_id = ctx.target.as_is_report_id
    if latest_report_id is None:
        return False
    return not any(
        artifact.type == "slides"
        and artifact.slide_kind == "discussion"
        and latest_report_id in artifact.derived_from
        for artifact in ctx.artifacts.values()
    )


def _readiness_driven_actions(ready: dict) -> list[dict]:
    """readinessの失敗条件を対応する行動へ写す。"""
    mapping = {
        "internal_as_is_missing": "elicit_internal_as_is",
        "unsupported_confirmed_to_be": "ground_confirmed_to_be",
        "to_be_go_ahead_missing": "request_to_be_go_ahead",
    }
    return [
        {
            "code": mapping[condition["code"]],
            **({"refs": condition["refs"]} if condition["refs"] else {}),
        }
        for condition in ready["failed_conditions"]
        if condition["code"] in mapping
    ]


def stale_artifact_ids(
    storage: Storage, project_id: str, knowledge_root: Path, today: date | None = None
) -> list[str]:
    report = project_status(storage, project_id, knowledge_root, today=today)
    return [row["id"] for row in report["artifacts"] if row["stale"]]
