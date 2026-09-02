"""生成物。必ず要件バージョンと引用ナレッジエントリに紐づく(なぜこの提案かを追跡可能)。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from medo_core.storage import Storage

ArtifactType = Literal[
    "research", "as-is-report",
    "architecture", "slides", "mock", "comparison", "mini-prfaq", "prfaq", "fermi",
]

SlideKind = Literal["discussion", "final"]

ALLOWED_PARENTS: dict[tuple[str, str | None], tuple[tuple[str, ...], bool]] = {
    ("as-is-report", None): (("research",), False),
    ("slides", "discussion"): (("as-is-report",), True),
    ("slides", "final"): (("prfaq",), True),
}

COVERAGE_TYPES = ("mini-prfaq", "prfaq", "comparison", "architecture", "mock")

REJECTION_TYPES = ("mini-prfaq", "comparison", "prfaq")


class OptionMeta(BaseModel):
    name: str
    approach_type: str = ""


class GrownFrom(BaseModel):
    artifact: str
    option: str


class RejectedOption(BaseModel):
    name: str
    reason: str
    accepted_risk: str = ""


class Artifact(BaseModel):
    project: str
    type: ArtifactType
    version: int = 1
    requirements_version: int
    cited_knowledge: list[str] = Field(default_factory=list)
    cited_facts: list[str] = Field(default_factory=list)
    options: list[OptionMeta] = Field(default_factory=list)
    grown_from: GrownFrom | None = None
    derived_from: list[str] = Field(default_factory=list)
    slide_kind: SlideKind | None = None
    covered_challenge_ids: list[str] | None = None
    rejected_options: list[RejectedOption] = Field(default_factory=list)
    generated_by: Literal["claude", "codex", "gemini"] | None = None
    content: str

    @model_validator(mode="after")
    def _validate_type_rules(self) -> "Artifact":
        if self.type == "prfaq" and self.grown_from is None:
            raise ValueError(
                "prfaq には grown_from(育成元のミニPRFAQ候補セットと打ち手)が必須です"
            )
        if self.type == "slides" and self.slide_kind is None:
            raise ValueError("slides には slide_kind(discussion|final)が必須です")
        if self.rejected_options and self.type not in REJECTION_TYPES:
            raise ValueError(
                f"rejected_options を持てるのは {'/'.join(REJECTION_TYPES)} のみです"
            )
        if self.type != "slides" and self.slide_kind is not None:
            raise ValueError("slide_kind は slides でのみ指定できます")
        if self.type == "fermi":
            if self.generated_by is not None:
                raise ValueError("fermi はコードが生成するため generated_by は指定できません")
        elif self.generated_by is None:
            raise ValueError(f"{self.type} には generated_by(claude|codex|gemini)が必須です")
        return self


class ArtifactStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _prefix(self, project_id: str) -> str:
        return f"projects/{project_id}/artifacts"

    def save(self, project_id: str, artifact: Artifact) -> str:
        existing = {a_id: a for a_id, a in self._load_all(project_id).items()}
        self._validate_parents(artifact, existing)
        self._validate_grown_from(artifact, existing)
        self._validate_version_monotonicity(artifact, existing)

        versions = [
            int(a_id.rsplit("-v", 1)[1])
            for a_id in existing
            if a_id.startswith(f"{artifact.type}-v")
        ]
        version = max(versions, default=0) + 1
        artifact = artifact.model_copy(update={"version": version, "project": project_id})
        artifact_id = f"{artifact.type}-v{version}"
        self._detect_cycle(artifact_id, artifact, existing)
        self._storage.put(
            f"{self._prefix(project_id)}/{artifact_id}", artifact.model_dump(mode="json")
        )
        return artifact_id

    def _load_all(self, project_id: str) -> dict[str, Artifact]:
        return {
            p.rsplit("/", 1)[1]: Artifact.model_validate(self._storage.get(p))
            for p in self._storage.list(self._prefix(project_id))
        }

    def _validate_parents(self, artifact: Artifact, existing: dict[str, Artifact]) -> None:
        rule = ALLOWED_PARENTS.get((artifact.type, artifact.slide_kind))
        if rule is None:
            if artifact.derived_from:
                raise ValueError(f"{artifact.type} は derived_from を持てません")
            return
        allowed_types, required = rule
        if required and len(artifact.derived_from) != 1:
            raise ValueError(
                f"{artifact.type}({artifact.slide_kind})の親はちょうど1件必要です"
            )
        if not required and len(artifact.derived_from) > 1:
            raise ValueError(f"{artifact.type} の親は0または1件です")
        for parent_id in artifact.derived_from:
            parent = existing.get(parent_id)
            if parent is None:
                raise ValueError(f"derived_from の親が存在しません: {parent_id}")
            if parent.type not in allowed_types:
                raise ValueError(
                    f"derived_from に許容されない親typeです: {parent_id}({parent.type})"
                )

    def _validate_grown_from(self, artifact: Artifact, existing: dict[str, Artifact]) -> None:
        if artifact.grown_from is None:
            return
        parent = existing.get(artifact.grown_from.artifact)
        if parent is None:
            raise ValueError(
                f"grown_from の候補セットが存在しません: {artifact.grown_from.artifact}"
            )
        if artifact.grown_from.option not in {o.name for o in parent.options}:
            raise ValueError(
                f"grown_from の打ち手が候補セットに存在しません: {artifact.grown_from.option}"
            )

    def _validate_version_monotonicity(
        self, artifact: Artifact, existing: dict[str, Artifact]
    ) -> None:
        same_type = [a for a in existing.values() if a.type == artifact.type]
        if not same_type:
            return
        newest = max(a.requirements_version for a in same_type)
        if artifact.requirements_version < newest:
            raise ValueError(
                f"同じtypeの既存最新版より古い requirements_version では保存できません"
                f"(既存: {newest} / 指定: {artifact.requirements_version})"
            )

    def _detect_cycle(
        self, artifact_id: str, artifact: Artifact, existing: dict[str, Artifact]
    ) -> None:
        graph = {a_id: a.derived_from for a_id, a in existing.items()}
        graph[artifact_id] = artifact.derived_from
        visiting: set[str] = set()

        def walk(node: str) -> None:
            if node in visiting:
                raise ValueError(f"derived_from が循環しています: {node}")
            visiting.add(node)
            for parent in graph.get(node, []):
                walk(parent)
            visiting.discard(node)

        walk(artifact_id)

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
