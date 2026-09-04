"""診断の素材を1回の走査で解決する。

status.py が収集と提示を兼ねると、1関数が3つの責務を持ちテストが
「何を検証しているか」を表せなくなる。
"""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from pydantic import BaseModel, PrivateAttr

from medo_core.artifacts import Artifact, ArtifactStore, Freshness
from medo_core.checks import (
    CheckState,
    detect_inconsistency,
    detect_ritualized,
    effective_checks,
)
from medo_core.config import get_knowledge_root
from medo_core.diagnostics import diagnostic_phase, round_delta
from medo_core.events import EventStore
from medo_core.facts import FactStore
from medo_core.knowledge import KnowledgeStore
from medo_core.manifest import ChangeManifest, ManifestStore
from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.responses import (
    ConvergenceTarget,
    EffectiveResponse,
    fold_responses,
    resolve_convergence_target,
)
from medo_core.storage import Storage
from medo_core.workflow import WorkflowRecorder


class StatusContext(BaseModel):
    project_id: str
    doc: RequirementsDoc
    previous_doc: RequirementsDoc | None
    phase: str
    include_scope: tuple[str, ...]
    target: ConvergenceTarget
    artifacts: dict[str, Artifact]
    freshness: dict[str, Freshness]
    manifests: list[ChangeManifest]
    events: list
    checks: dict[str, CheckState]
    responses: list[EffectiveResponse]
    round_count: int
    pending_milestones: list[str]
    focus_hypothesis: str
    open_review_findings: list[str]
    resolved_objections: int

    _round_documents: list[tuple[int, RequirementsDoc | None, RequirementsDoc]] = (
        PrivateAttr(default_factory=list)
    )


def make_citation_checker(
    storage: Storage, project_id: str, knowledge_root: Path | None = None
) -> Callable[[Artifact, date | None], list[str]]:
    """生成物のうち、欠落またはstaleな引用IDを返す判定関数を作る。"""
    facts = FactStore(storage)
    knowledge = KnowledgeStore(
        knowledge_root if knowledge_root is not None else get_knowledge_root()
    )

    def citation_checker(artifact: Artifact, today: date | None) -> list[str]:
        stale = []
        for fact_id in artifact.cited_facts:
            fact = facts.get(project_id, fact_id)
            if fact is None or fact.is_stale(today=today):
                stale.append(fact_id)
        for entry_id in artifact.cited_knowledge:
            if "-" not in entry_id:
                stale.append(entry_id)
                continue
            kind, _ = entry_id.rsplit("-", 1)
            entry = knowledge.get(kind, entry_id)
            if entry is None or entry.is_stale(today=today):
                stale.append(entry_id)
        return stale

    return citation_checker


def collect(
    storage: Storage,
    project_id: str,
    *,
    include_scope: tuple[str, ...] = ("core",),
    today: date | None = None,
    knowledge_root: Path | None = None,
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
        is_citation_stale=make_citation_checker(storage, project_id, knowledge_root),
        today=today,
    )

    responses = fold_responses(events, target, artifacts, manifests)
    checks = effective_checks(
        events, phase=diagnostic_phase(doc), latest_requirements_version=version,
        manifests=manifests, current_artifact_ids=_current_artifact_ids(artifacts),
    )
    ctx = StatusContext(
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
    ctx._round_documents = _round_documents(reqs, project_id, manifests)
    return ctx


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
    approved = [
        artifacts[e.target.artifact_id]
        for e in reviews
        if e.outcome == "approved" and e.target.artifact_id in artifacts
    ]
    node_state = {
        n.id: n.confidence
        for section in ("gaps", "challenges", "open_questions")
        for n in getattr(doc, section)
    }
    open_refs: list[str] = []
    for event in reviews:
        if event.outcome != "changes_requested":
            continue
        reviewed = artifacts.get(event.target.artifact_id)
        if reviewed and any(
            successor.type == reviewed.type and successor.version > reviewed.version
            for successor in approved
        ):
            continue
        if event.slide_findings:
            open_refs.append(event.id)
        open_refs.extend(
            ref for ref in event.finding_refs
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


def _go_ahead_summary(ctx: StatusContext) -> dict:
    decision_makers = sorted(
        stakeholder.id for stakeholder in ctx.doc.stakeholders
        if stakeholder.is_decision_maker
    )
    agreed = sorted(
        response.stakeholder_id for response in ctx.responses
        if response.stakeholder_id in decision_makers
        and response.purpose == "to_be_go_ahead"
        and response.reaction == "agreed"
        and not response.expired
    )
    return {
        "decision_maker": agreed[0] if agreed else decision_makers[0] if decision_makers else "",
        "agreed": bool(agreed),
    }


def _round_documents(
    requirements: RequirementsStore,
    project_id: str,
    manifests: list[ChangeManifest],
) -> list[tuple[int, RequirementsDoc | None, RequirementsDoc]]:
    completed = []
    state = "waiting_as_is"
    before_round_version = 0
    round_id = 0
    for manifest in manifests:
        sections = {
            change.section
            for change in manifest.changes
            if change.change_kind == "substantive"
        }
        if not sections:
            continue
        if state == "waiting_as_is" and "as_is" in sections:
            before_round_version = manifest.version - 1
            state = "waiting_to_be"
        if state == "waiting_to_be" and "to_be" in sections:
            round_id += 1
            previous = (
                requirements.get(project_id, before_round_version)
                if before_round_version > 0
                else None
            )
            saved = requirements.get(project_id, manifest.version)
            if saved is not None:
                completed.append((round_id, previous, saved))
            state = "waiting_as_is"
    return completed


def _is_diverging(ctx: StatusContext, delta: dict) -> bool:
    if ctx.round_count < 2:
        return False
    if len(ctx._round_documents) < 2:
        return delta["progress_count"] == 0 and round_delta(
            ctx.previous_doc, ctx.doc, ctx.events, ctx.round_count - 1,
        )["progress_count"] == 0

    deltas = []
    previous_resolved = 0
    for round_id, previous, saved in ctx._round_documents:
        events = [event for event in ctx.events if event.round_id <= round_id]
        manifests = [manifest for manifest in ctx.manifests if manifest.version <= saved.version]
        target = resolve_convergence_target(saved.version, ctx.artifacts)
        responses = fold_responses(events, target, ctx.artifacts, manifests)
        resolved = _resolved_objections(events, responses)
        deltas.append(round_delta(
            previous, saved, events, round_id,
            resolved_objections=max(0, resolved - previous_resolved),
        ))
        previous_resolved = resolved
    return all(item["progress_count"] == 0 for item in deltas[-2:])


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
