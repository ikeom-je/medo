"""要件の版ごとの変更記録。

陳腐化判定は「生成物の要件版から最新版まで」を比較するため、保存時にしか
分からない情報(editorial宣言・ID初回採番)を後から再現できる必要がある。
"""

from typing import Literal

from pydantic import BaseModel, Field

from medo_core.storage import Storage

TRACKED_SECTIONS = [
    "industry", "background", "goal", "principles", "functional", "non_functional",
    "sources", "as_is", "to_be", "kpis", "stakeholders", "gaps", "bottlenecks",
    "challenges", "constraints", "attempts", "hypotheses", "open_questions",
]


class SectionChange(BaseModel):
    section: str
    change_kind: Literal["substantive", "editorial"] = "substantive"


class ChangeManifest(BaseModel):
    version: int
    changes: list[SectionChange] = Field(default_factory=list)
    id_only_migration: bool = False
    recorded_on: str


EMPTY_SECTION = {"non_functional": {}, "industry": "", "background": "", "goal": ""}


def changed_sections(old: dict, new: dict) -> list[str]:
    """2つの要件ドキュメント(dict)で値が異なるセクション名を返す。

    意味差の推測はしない。値が異なるかどうかだけを見る。
    初版(old={})では、既定値のまま埋まっていないセクションを変更として数えない。
    """
    def value(doc: dict, section: str):
        return doc.get(section, EMPTY_SECTION.get(section, []))

    return [s for s in TRACKED_SECTIONS if value(old, s) != value(new, s)]


def is_text_only_change(section: str, old: dict, new: dict) -> bool:
    """そのセクションの差分が text の書き換えだけかを判定する。

    editorial 宣言を無条件に信じると、ノードの追加・削除や confidence 変更まで
    「誤字修正」として陳腐化判定から隠せてしまう。宣言できる範囲を機械的に絞る。
    """
    old_nodes = old.get(section) or []
    new_nodes = new.get(section) or []
    if not isinstance(old_nodes, list) or not isinstance(new_nodes, list):
        return section in ("goal", "background", "industry")
    if len(old_nodes) != len(new_nodes):
        return False
    for before, after in zip(old_nodes, new_nodes, strict=True):
        if {k: v for k, v in before.items() if k != "text"} != \
                {k: v for k, v in after.items() if k != "text"}:
            return False
    return True


def fold_sections(
    manifests: list[ChangeManifest], from_version: int, change_kind: str
) -> set[str]:
    """from_version より後の全manifestを畳み込み、指定種別の変更セクションを返す。"""
    sections: set[str] = set()
    for m in manifests:
        if m.version <= from_version or m.id_only_migration:
            continue
        sections.update(c.section for c in m.changes if c.change_kind == change_kind)
    return sections


def fold_substantive_sections(
    manifests: list[ChangeManifest], from_version: int
) -> set[str]:
    return fold_sections(manifests, from_version, "substantive")


class ManifestStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _prefix(self, project_id: str) -> str:
        return f"projects/{project_id}/manifests"

    def save(self, project_id: str, manifest: ChangeManifest) -> None:
        self._storage.put(
            f"{self._prefix(project_id)}/v{manifest.version}",
            manifest.model_dump(mode="json"),
        )

    def list(self, project_id: str) -> list[ChangeManifest]:
        manifests = [
            ChangeManifest.model_validate(self._storage.get(p))
            for p in self._storage.list(self._prefix(project_id))
        ]
        return sorted(manifests, key=lambda m: m.version)
