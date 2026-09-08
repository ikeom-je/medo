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
    on_current_target: bool = False


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
            on_current_target=bool(current),
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
