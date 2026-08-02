"""生成物。必ず要件バージョンと引用カタログエントリに紐づく(なぜこの提案かを追跡可能)。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from medo_core.storage import Storage

ArtifactType = Literal[
    "architecture", "slides", "mock", "comparison", "mini-prfaq", "prfaq", "fermi"
]


class OptionMeta(BaseModel):
    name: str
    approach_type: str = ""


class GrownFrom(BaseModel):
    artifact: str
    option: str


class Artifact(BaseModel):
    project: str
    type: ArtifactType
    version: int = 1
    requirements_version: int
    cited_knowledge: list[str] = Field(default_factory=list)
    cited_facts: list[str] = Field(default_factory=list)
    options: list[OptionMeta] = Field(default_factory=list)
    grown_from: GrownFrom | None = None
    generated_by: Literal["claude", "gemini"] | None = None
    content: str

    @model_validator(mode="after")
    def _validate_type_rules(self) -> "Artifact":
        if self.type == "prfaq" and self.grown_from is None:
            raise ValueError(
                "prfaq には grown_from(育成元のミニPRFAQ候補セットと打ち手)が必須です"
            )
        if self.type == "fermi":
            if self.generated_by is not None:
                raise ValueError(
                    "fermi はコードが生成するため generated_by は指定できません"
                )
        elif self.generated_by is None:
            raise ValueError(f"{self.type} には generated_by(claude|gemini)が必須です")
        return self


class ArtifactStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _prefix(self, project_id: str) -> str:
        return f"projects/{project_id}/artifacts"

    def save(self, project_id: str, artifact: Artifact) -> str:
        existing = [
            p.rsplit("/", 1)[1]
            for p in self._storage.list(self._prefix(project_id))
        ]
        versions = [
            int(name.rsplit("-v", 1)[1])
            for name in existing
            if name.startswith(f"{artifact.type}-v")
        ]
        version = max(versions, default=0) + 1
        artifact = artifact.model_copy(update={"version": version, "project": project_id})
        artifact_id = f"{artifact.type}-v{version}"
        self._storage.put(
            f"{self._prefix(project_id)}/{artifact_id}", artifact.model_dump(mode="json")
        )
        return artifact_id

    def get(self, project_id: str, artifact_id: str) -> Artifact | None:
        raw = self._storage.get(f"{self._prefix(project_id)}/{artifact_id}")
        return Artifact.model_validate(raw) if raw else None

    def list(self, project_id: str) -> list[Artifact]:
        return [
            Artifact.model_validate(self._storage.get(p))
            for p in self._storage.list(self._prefix(project_id))
        ]

    def stale_artifacts(self, project_id: str, current_requirements_version: int) -> list[Artifact]:
        return [
            a for a in self.list(project_id)
            if a.requirements_version < current_requirements_version
        ]
