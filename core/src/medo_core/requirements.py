"""要件ドキュメント(ハブ)。バージョンは保存のたびに自動インクリメント、旧版保持。"""

from typing import Literal

from pydantic import BaseModel, Field

from medo_core.storage import Storage

Confidence = Literal["confirmed", "assumed", "open"]


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
    challenges: list[ConfidenceItem] = Field(default_factory=list)  # 課題(What/Whyの起点)
    functional: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional: dict[str, str] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    knowledge_backend: Literal["markdown", "sqlite"] = "markdown"


class RequirementsStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _path(self, project_id: str, version: int) -> str:
        return f"projects/{project_id}/requirements/v{version}"

    def latest_version(self, project_id: str) -> int:
        paths = self._storage.list(f"projects/{project_id}/requirements")
        versions = [int(p.rsplit("/v", 1)[1]) for p in paths]
        return max(versions, default=0)

    def save(self, project_id: str, doc: RequirementsDoc) -> int:
        version = self.latest_version(project_id) + 1
        doc = doc.model_copy(update={"version": version, "project": project_id})
        self._storage.put(self._path(project_id, version), doc.model_dump(mode="json"))
        return version

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
        old_q = set(old.open_questions)
        new_q = set(new.open_questions)
        empty.update(
            functional_added=sorted(new_f - old_f),
            functional_removed=sorted(old_f - new_f),
            open_questions_added=sorted(new_q - old_q),
            open_questions_resolved=sorted(old_q - new_q),
        )
        return empty
