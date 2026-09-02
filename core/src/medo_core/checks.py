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
