"""プロジェクトの現在地レポート。保存状態から決定論的に導出し、LLMを挟まない。"""

from __future__ import annotations

from datetime import date

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.catalog import CatalogStore
from medo_core.facts import Fact, FactStore
from medo_core.requirements import RequirementsStore
from medo_core.storage import Storage


def _catalog_entry_stale(store: CatalogStore, entry_id: str, today: date | None) -> bool:
    """引用カタログエントリがstaleまたは欠落ならTrue。"""
    if "__" not in entry_id:
        return True
    service, feature = entry_id.split("__", 1)
    entry = store.get(service, feature)
    return entry is None or entry.is_stale(today=today)


def _artifact_stale(
    artifact: Artifact,
    current_version: int,
    facts_by_id: dict[str, Fact],
    cat_store: CatalogStore,
    today: date | None,
) -> bool:
    if artifact.requirements_version < current_version:
        return True
    for fact_id in artifact.cited_facts:
        fact = facts_by_id.get(fact_id)
        if fact is None or fact.is_stale(today=today):
            return True
    return any(
        _catalog_entry_stale(cat_store, entry_id, today)
        for entry_id in artifact.cited_catalog_entries
    )


def project_status(storage: Storage, project_id: str, today: date | None = None) -> dict:
    req_store = RequirementsStore(storage)
    version = req_store.latest_version(project_id)
    if version == 0:
        return {
            "project": project_id,
            "requirements": None,
            "facts": {"count": 0, "stale": 0},
            "artifacts": [],
            "next_step": "hearing",
        }

    doc = req_store.get(project_id)
    counts = {"confirmed": 0, "assumed": 0, "open": 0}
    for item in [*doc.functional, *doc.principles, *doc.challenges]:
        counts[item.confidence] += 1

    facts = FactStore(storage).list(project_id)
    facts_by_id = {f.fact_id: f for f in facts}
    cat_store = CatalogStore(storage)

    # typeごとの最新バージョンのみを対象にする(旧版のstaleに引きずられて
    # 再生成後も up-to-date に到達できない事態を防ぐ)。type昇順で決定論的に返す
    latest_by_type: dict[str, Artifact] = {}
    for a in ArtifactStore(storage).list(project_id):
        current = latest_by_type.get(a.type)
        if current is None or a.version > current.version:
            latest_by_type[a.type] = a
    artifact_rows = [
        {
            "id": f"{a.type}-v{a.version}",
            "type": a.type,
            "requirements_version": a.requirements_version,
            "stale": _artifact_stale(a, version, facts_by_id, cat_store, today),
        }
        for a in sorted(latest_by_type.values(), key=lambda a: a.type)
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
        "project": project_id,
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


def stale_artifact_ids(storage: Storage, project_id: str, today: date | None = None) -> list[str]:
    report = project_status(storage, project_id, today=today)
    return [row["id"] for row in report["artifacts"] if row["stale"]]
