"""要件ドキュメント(ハブ)。バージョンは保存のたびに自動インクリメント、旧版保持。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from medo_core.manifest import (
    ChangeManifest,
    ManifestStore,
    SectionChange,
    changed_sections,
    is_text_only_change,
)
from medo_core.nodes import (
    ID_PREFIXES,
    AsIs,
    Attempt,
    Bottleneck,
    Challenge,
    Confidence,
    Constraint,
    Gap,
    Hypothesis,
    Kpi,
    OpenQuestion,
    Stakeholder,
    ToBe,
)
from medo_core.storage import Storage
from medo_core.watermark import IdWatermarkStore

LINK_FIELDS = {
    "gaps": {"from_as_is": "as_is", "from_to_be": "to_be"},
    "bottlenecks": {"gap_ids": "gaps"},
    "challenges": {
        "bottleneck_ids": "bottlenecks",
        "cause_hypothesis_ids": "hypotheses",
    },
    "kpis": {"to_be_ids": "to_be"},
    "attempts": {"challenge_ids": "challenges", "gap_ids": "gaps"},
    "hypotheses": {"challenge_ids": "challenges"},
    "as_is": {"source_stakeholder_ids": "stakeholders"},
}


class ConfidenceItem(BaseModel):
    text: str
    confidence: Confidence = "open"


class FunctionalRequirement(ConfidenceItem):
    """機能要件。後方互換のため名前を維持(実体はConfidenceItem)。"""


class RequirementsDoc(BaseModel):
    project: str
    version: int = 1
    industry: str = ""
    background: str = ""  # 業界・ビジネス状況の要約
    goal: str = ""
    principles: list[ConfidenceItem] = Field(default_factory=list)  # 経営思想・理念・方針
    functional: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional: dict[str, str] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)
    knowledge_backend: Literal["markdown", "sqlite"] = "markdown"

    challenges: list[Challenge] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)

    as_is: list[AsIs] = Field(default_factory=list)
    to_be: list[ToBe] = Field(default_factory=list)
    kpis: list[Kpi] = Field(default_factory=list)
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    bottlenecks: list[Bottleneck] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    attempts: list[Attempt] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)

    @field_validator("open_questions", mode="before")
    @classmethod
    def _accept_legacy_string_list(cls, value):
        if isinstance(value, list):
            return [{"text": v} if isinstance(v, str) else v for v in value]
        return value


class RequirementsStore:
    def __init__(self, storage: Storage):
        self._storage = storage
        self._watermarks = IdWatermarkStore(storage)
        self._manifests = ManifestStore(storage)

    def _path(self, project_id: str, version: int) -> str:
        return f"projects/{project_id}/requirements/v{version}"

    def latest_version(self, project_id: str) -> int:
        paths = self._storage.list(f"projects/{project_id}/requirements")
        versions = [int(p.rsplit("/v", 1)[1]) for p in paths]
        return max(versions, default=0)

    def save(
        self,
        project_id: str,
        doc: RequirementsDoc,
        *,
        editorial_sections: tuple[str, ...] = (),
        today: date | None = None,
    ) -> int:
        previous = self.get(project_id)
        self._reject_duplicate_ids(doc)
        self._reject_unknown_existing_ids(doc, previous)
        doc = self._assign_ids(project_id, doc)
        self._validate_links(doc)
        self._validate_domain_rules(doc)

        version = self.latest_version(project_id) + 1
        doc = doc.model_copy(update={"version": version, "project": project_id})
        self._storage.put(self._path(project_id, version), doc.model_dump(mode="json"))
        self._record_manifest(project_id, previous, doc, editorial_sections, today)
        return version

    def _iter_sections(self, doc: RequirementsDoc):
        for section in ID_PREFIXES:
            yield section, getattr(doc, section)

    def _reject_duplicate_ids(self, doc: RequirementsDoc) -> None:
        seen: set[str] = set()
        for _, nodes in self._iter_sections(doc):
            for n in nodes:
                if not n.id:
                    continue
                if n.id in seen:
                    raise ValueError(f"IDが重複しています: {n.id}")
                seen.add(n.id)

    def _reject_unknown_existing_ids(
        self, doc: RequirementsDoc, previous: RequirementsDoc | None
    ) -> None:
        known = set()
        if previous:
            for _, nodes in self._iter_sections(previous):
                known.update(n.id for n in nodes if n.id)
        for _, nodes in self._iter_sections(doc):
            for n in nodes:
                if n.id and n.id not in known:
                    raise ValueError(
                        f"直前バージョンに存在しないIDです: {n.id}"
                        "(リナンバリングは許可されません)"
                    )

    def _assign_ids(self, project_id: str, doc: RequirementsDoc) -> RequirementsDoc:
        watermark = self._watermarks.load(project_id)
        updates = {}
        for section, nodes in self._iter_sections(doc):
            blanks = [i for i, n in enumerate(nodes) if not n.id]
            if not blanks:
                continue
            new_ids = watermark.allocate(ID_PREFIXES[section], len(blanks))
            assigned = list(nodes)
            for i, new_id in zip(blanks, new_ids, strict=True):
                assigned[i] = assigned[i].model_copy(update={"id": new_id})
            updates[section] = assigned
        self._watermarks.save(project_id, watermark)
        return doc.model_copy(update=updates) if updates else doc

    def _validate_links(self, doc: RequirementsDoc) -> None:
        ids_by_section = {
            section: {n.id for n in nodes} for section, nodes in self._iter_sections(doc)
        }
        for section, fields in LINK_FIELDS.items():
            for node in getattr(doc, section):
                for field, target in fields.items():
                    for ref in getattr(node, field):
                        if ref not in ids_by_section[target]:
                            raise ValueError(
                                f"{section}.{field} の参照先が存在しません: {ref}"
                            )

    def _validate_domain_rules(self, doc: RequirementsDoc) -> None:
        as_is_by_id = {n.id: n for n in doc.as_is}

        for gap in doc.gaps:
            refs = [as_is_by_id[i] for i in gap.from_as_is]
            if gap.kind == "perception":
                kinds = {n.visibility for n in refs}
                if kinds != {"public", "internal"}:
                    raise ValueError(
                        "perception gap は public と internal の AsIs を"
                        "それぞれ1件以上参照する必要があります"
                    )
            if gap.kind == "internal_conflict":
                internals = [n for n in refs if n.visibility == "internal"]
                stakeholder_sets = {frozenset(n.source_stakeholder_ids) for n in internals}
                if len(internals) < 2 or len(stakeholder_sets) < 2:
                    raise ValueError(
                        "internal_conflict gap は視点の異なる internal な AsIs を"
                        "2件以上参照する必要があります"
                    )
            if gap.kind != "goal" and gap.from_to_be:
                raise ValueError(f"{gap.kind} gap は from_to_be を持てません")

        goal_gap_ids = {g.id for g in doc.gaps if g.kind == "goal"}
        for bn in doc.bottlenecks:
            if bn.confidence != "confirmed":
                raise ValueError(
                    f"bottleneck {bn.id} は confirmed のみ保存できます"
                    "(未検証の真因は hypotheses(kind='cause')に置く)"
                )
            for gid in bn.gap_ids:
                if gid not in goal_gap_ids:
                    raise ValueError(f"bottleneck が参照できるのは goal gap のみです: {gid}")

        conflict_gap_ids = {g.id for g in doc.gaps if g.kind == "internal_conflict"}
        for ch in doc.challenges:
            src = ch.promoted_from
            if src and src.kind == "internal_conflict" and src.ref not in conflict_gap_ids:
                raise ValueError(
                    "promoted_from(internal_conflict)の参照先が"
                    f"internal_conflict gap ではありません: {src.ref}"
                )

        validated_causes = {
            h.id
            for h in doc.hypotheses
            if h.kind == "cause" and h.status == "validated"
        }
        for bn in doc.bottlenecks:
            if bn.from_hypothesis and bn.from_hypothesis not in validated_causes:
                raise ValueError(
                    "from_hypothesis は kind='cause' かつ status='validated' の仮説のみ"
                    f"参照できます: {bn.from_hypothesis}"
                )

        node_ids = {n.id for _, nodes in self._iter_sections(doc) for n in nodes}
        for tb in doc.to_be:
            for ref in tb.evidenced_by:
                if not ref.startswith("ev-") and ref not in node_ids:
                    raise ValueError(f"evidenced_by の参照先が存在しません: {ref}")

    def _record_manifest(
        self,
        project_id: str,
        previous: RequirementsDoc | None,
        saved: RequirementsDoc,
        editorial_sections: tuple[str, ...],
        today: date | None,
    ) -> None:
        old = previous.model_dump(mode="json") if previous else {}
        new = saved.model_dump(mode="json")
        sections = changed_sections(old, new)
        editorial_sections = tuple(
            s for s in editorial_sections if is_text_only_change(s, old, new)
        )
        id_only = previous is not None and self._is_id_only_change(previous, saved)
        self._manifests.save(
            project_id,
            ChangeManifest(
                version=saved.version,
                changes=[
                    SectionChange(
                        section=s,
                        change_kind=(
                            "editorial" if s in editorial_sections else "substantive"
                        ),
                    )
                    for s in sections
                ],
                id_only_migration=id_only,
                recorded_on=(today or date.today()).isoformat(),
            ),
        )

    def _is_id_only_change(
        self, previous: RequirementsDoc, saved: RequirementsDoc
    ) -> bool:
        """ID以外のフィールドが同一なら初回採番のみの保存とみなす。"""

        def strip_ids(doc: RequirementsDoc) -> dict:
            data = doc.model_dump(mode="json")
            for section in ID_PREFIXES:
                for node in data.get(section, []):
                    node.pop("id", None)
            data.pop("version", None)
            return data

        return strip_ids(previous) == strip_ids(saved)

    def get(self, project_id: str, version: int | None = None) -> RequirementsDoc | None:
        if version is None:
            version = self.latest_version(project_id)
            if version == 0:
                return None
        raw = self._storage.get(self._path(project_id, version))
        return RequirementsDoc.model_validate(raw) if raw else None

    def diff(self, project_id: str) -> dict:
        to_v = self.latest_version(project_id)
        from_v = to_v - 1 if to_v > 1 else 0
        empty = {
            "from": from_v,
            "to": to_v,
            "functional_added": [],
            "functional_removed": [],
            "open_questions_added": [],
            "open_questions_resolved": [],
        }
        if from_v == 0:
            return empty
        old = self.get(project_id, from_v)
        new = self.get(project_id, to_v)
        old_f = {f.text for f in old.functional}
        new_f = {f.text for f in new.functional}
        old_q = {q.text for q in old.open_questions}
        new_q = {q.text for q in new.open_questions}
        empty.update(
            functional_added=sorted(new_f - old_f),
            functional_removed=sorted(old_f - new_f),
            open_questions_added=sorted(new_q - old_q),
            open_questions_resolved=sorted(old_q - new_q),
        )
        return empty
