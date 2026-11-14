"""ナレッジ統合の決定論部分。外部の判定結果を受け取り、生成物への影響を読む。"""

from __future__ import annotations

import re
import unicodedata
from itertools import combinations
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel

from medo_core.artifacts import ArtifactStore
from medo_core.context import make_citation_checker
from medo_core.knowledge import KnowledgeEntry
from medo_core.requirements import RequirementsStore
from medo_core.source_check import _without_annotation
from medo_core.storage import Storage


def _url_key(source: str) -> str | None:
    u = urlparse(source)
    if u.scheme not in ("http", "https") or not u.hostname:
        return None
    path = re.sub(r"\.(pdf|html?)$", "", u.path.rstrip("/"), flags=re.IGNORECASE)
    host = u.hostname.lower()
    if host == "arxiv.org" or host.endswith(".arxiv.org"):
        path = re.sub(r"^/(abs|pdf)/", "/paper/", path)
    return f"{u.netloc.lower()}{path}"


def _bigrams(text: str) -> set[str]:
    t = "".join(unicodedata.normalize("NFKC", text).split())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _overlap(a: str, b: str) -> float:
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def candidate_pairs(
    entries: list[KnowledgeEntry], overlap_threshold: float = 0.35,
) -> list[tuple[str, str]]:
    live = sorted(
        (e for e in entries if not e.is_superseded),
        key=lambda e: (e.kind, int(e.entry_id.rsplit("-", 1)[1])),
    )
    pairs = []
    for a, b in combinations(live, 2):
        if a.kind != b.kind:
            continue
        url_a, url_b = _url_key(a.source), _url_key(b.source)
        same_url = url_a is not None and url_a == url_b
        unit_a, unit_b = _without_annotation(a.unit), _without_annotation(b.unit)
        same_unit = bool(unit_a) and unit_a == unit_b
        if same_url or same_unit or _overlap(a.statement, b.statement) >= overlap_threshold:
            pairs.append((a.entry_id, b.entry_id))
    return pairs


class PairJudgment(BaseModel):
    relation: str
    relation_confidence: float
    same_scope: float
    newer: str
    newer_confidence: float
    keep: str
    keep_confidence: float


class Routing(BaseModel):
    bucket: Literal["proposal", "conflict", "excluded", "requery", "held"]
    old: str = ""
    by: str = ""
    reason: Literal["", "duplicate", "updates"] = ""


def _pick(a: KnowledgeEntry, b: KnowledgeEntry, side: str) -> tuple[str, str]:
    return (b.entry_id, a.entry_id) if side == "a" else (a.entry_id, b.entry_id)


def route(
    a: KnowledgeEntry, b: KnowledgeEntry, j: PairJudgment, threshold: float = 0.8,
) -> Routing:
    t = threshold
    units_match = _without_annotation(a.unit) == _without_annotation(b.unit)
    if j.relation == "conflicting":
        return Routing(bucket="conflict")
    if (j.relation == "duplicate" and j.relation_confidence >= t and j.same_scope >= t
            and units_match and a.value is not None and b.value is not None
            and a.value != b.value):
        return Routing(bucket="conflict")
    if j.relation in ("complementary", "unrelated") and j.relation_confidence >= t:
        return Routing(bucket="excluded")
    one_sided = (a.value is None) != (b.value is None)
    if (j.relation == "duplicate" and j.relation_confidence >= t and j.same_scope >= t
            and j.newer == "same" and j.newer_confidence >= t and j.keep in ("a", "b")
            and j.keep_confidence >= t and units_match and not one_sided):
        old, by = _pick(a, b, j.keep)
        return Routing(bucket="proposal", old=old, by=by, reason="duplicate")
    if (j.relation == "updates" and j.relation_confidence >= t and j.same_scope >= t
            and j.newer in ("a", "b") and j.newer_confidence >= t):
        old, by = _pick(a, b, j.newer)
        return Routing(bucket="proposal", old=old, by=by, reason="updates")
    required = [j.relation_confidence, j.same_scope, j.newer_confidence]
    if j.relation == "duplicate":
        required.append(j.keep_confidence)
    if (j.relation_confidence >= 0.5 and j.relation in ("duplicate", "updates")
            and any(score < t for score in required)):
        return Routing(bucket="requery")
    return Routing(bucket="held")


def check_components(
    proposals: list[Routing], conflicts: list[tuple[str, str]],
) -> tuple[list[Routing], list[Routing]]:
    graph: dict[str, set[str]] = {}
    successors: dict[str, set[str]] = {}
    for p in proposals:
        graph.setdefault(p.old, set()).add(p.by)
        graph.setdefault(p.by, set()).add(p.old)
        successors.setdefault(p.old, set()).add(p.by)

    visited: set[str] = set()
    blocked: set[str] = set()
    for node in graph:
        if node in visited:
            continue
        component: set[str] = set()
        pending = [node]
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(graph[current] - component)
        visited.update(component)
        has_conflict = any(a in component and b in component for a, b in conflicts)
        has_branch = any(len(successors.get(n, ())) > 1 for n in component)
        has_chain = any(p.by in successors for p in proposals if p.old in component)
        if has_conflict or has_branch or has_chain:
            blocked.update(component)

    keep = [p for p in proposals if p.old not in blocked]
    held = [p for p in proposals if p.old in blocked]
    return keep, held


def affected_artifacts(
    storage: Storage, knowledge_root: Path, kind: str, entry_id: str,
) -> list[dict]:
    """指定エントリの直接引用と、statusと同じ鮮度伝播で影響を受ける子孫を返す。"""
    if entry_id.rsplit("-", 1)[0] != kind:
        return []
    store = ArtifactStore(storage)
    reqs = RequirementsStore(storage)
    rows = []
    for project in storage.list_children("projects"):
        artifacts = store._load_all(project)
        affected = {
            a_id: "cited" for a_id, artifact in artifacts.items()
            if entry_id in artifact.cited_knowledge
        }
        if not affected:
            continue
        doc = reqs.get(project)
        core_ids = {c.id for c in doc.challenges if c.scope == "core"} if doc else set()
        freshness = store.freshness(
            project, reqs.latest_version(project), core_ids,
            is_citation_stale=make_citation_checker(storage, project, knowledge_root),
        )
        changed = True
        while changed:
            changed = False
            for a_id, artifact in artifacts.items():
                if a_id in affected or freshness[a_id].state != "stale":
                    continue
                # grown_fromは選択の来歴で、内容依存ではないため伝播しない。
                parent = next((p for p in artifact.derived_from if p in affected), None)
                if parent is not None:
                    affected[a_id] = parent
                    changed = True
        rows.extend(
            {"project": project, "artifact": a_id, "via": affected[a_id]}
            for a_id in sorted(affected)
        )
    return rows
