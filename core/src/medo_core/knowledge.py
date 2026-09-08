"""技術ナレッジ(案件横断)。出典必須・frontmatter付きmdでgit履歴レビュー前提。"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlparse

import sqlite3
import yaml
from pydantic import BaseModel, model_validator

KnowledgeKind = Literal["tech", "market", "policy", "trend", "company"]
_URL_KINDS = {"tech", "market", "policy", "trend"}
_STALE_THRESHOLD_DAYS = {"tech": 30}
_DEFAULT_STALE_THRESHOLD_DAYS = 180


class KnowledgeEntry(BaseModel):
    entry_id: str = ""
    kind: KnowledgeKind
    statement: str
    value: float | None = None
    unit: str = ""
    source: str
    retrieved: str  # ISO日付 YYYY-MM-DD
    note: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "KnowledgeEntry":
        if not self.source.strip():
            raise ValueError("source は必須です(出典のないナレッジは保存できません)")
        if self.kind in _URL_KINDS:
            parsed = urlparse(self.source)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"kind={self.kind} の source はURLである必要があります")
        try:
            date.fromisoformat(self.retrieved)
        except ValueError as e:
            raise ValueError(f"retrieved はISO日付(YYYY-MM-DD)である必要があります: {e}") from e
        return self

    def is_stale(self, today: date | None = None) -> bool:
        today = today or date.today()
        threshold = _STALE_THRESHOLD_DAYS.get(self.kind, _DEFAULT_STALE_THRESHOLD_DAYS)
        return (today - date.fromisoformat(self.retrieved)).days > threshold


def _write_frontmatter(path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    path.write_text(f"---\n{front}---\n", encoding="utf-8")


def _read_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    _, front, _ = text.split("---", 2)
    return yaml.safe_load(front)


class KnowledgeStore:
    """`root/{kind}/{entry_id}.md` にfrontmatterで保存する。Storage Protocolは使わない。"""

    def __init__(self, root: Path):
        self._root = Path(root)

    def _dir(self, kind: str) -> Path:
        return self._root / kind

    def save(self, entry: KnowledgeEntry) -> str:
        if not entry.entry_id:
            nums = []
            d = self._dir(entry.kind)
            if d.is_dir():
                for f in d.glob(f"{entry.kind}-*.md"):
                    m = re.fullmatch(rf"{entry.kind}-(\d+)", f.stem)
                    if m:
                        nums.append(int(m.group(1)))
            entry = entry.model_copy(update={"entry_id": f"{entry.kind}-{max(nums, default=0) + 1}"})
        path = self._dir(entry.kind) / f"{entry.entry_id}.md"
        _write_frontmatter(path, entry.model_dump(mode="json", exclude={"entry_id"}))
        return entry.entry_id

    def get(self, kind: str, entry_id: str) -> KnowledgeEntry | None:
        path = self._dir(kind) / f"{entry_id}.md"
        if not path.exists():
            return None
        meta = _read_frontmatter(path)
        return KnowledgeEntry.model_validate({**meta, "entry_id": entry_id, "kind": kind})

    def search(self, query: str = "", kind: str | None = None, limit: int = 10) -> list[KnowledgeEntry]:
        q = query.lower()
        kinds = [kind] if kind else [d.name for d in self._root.iterdir() if d.is_dir()] if self._root.is_dir() else []
        results: list[KnowledgeEntry] = []
        for k in sorted(kinds):
            for path in sorted(self._dir(k).glob(f"{k}-*.md")):
                meta = _read_frontmatter(path)
                entry = KnowledgeEntry.model_validate({**meta, "entry_id": path.stem, "kind": k})
                haystack = " ".join([entry.statement, entry.note]).lower()
                if q and q not in haystack:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    return results
        return results





class ProjectKnowledgeEntry(BaseModel):
    entry_id: str = ""
    project: str
    statement: str
    source: str
    retrieved: str
    note: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ProjectKnowledgeEntry":
        if not self.statement.strip():
            raise ValueError("statement は必須です")
        if not self.source.strip():
            raise ValueError("source は必須です(対話メモでも出典表記は必須)")
        try:
            date.fromisoformat(self.retrieved)
        except ValueError as e:
            raise ValueError(f"retrieved はISO日付(YYYY-MM-DD)である必要があります: {e}") from e
        return self


class KnowledgeBackend(Protocol):
    def append(self, entry: ProjectKnowledgeEntry) -> str: ...
    def list(self, project: str) -> list[ProjectKnowledgeEntry]: ...
    def search(self, project: str, query: str) -> list[ProjectKnowledgeEntry]: ...


class MarkdownKnowledgeBackend:
    """`root/{project}/{entry_id}.md` にfrontmatterで追記専用保存する。"""

    def __init__(self, root: Path):
        self._root = Path(root)

    def _dir(self, project: str) -> Path:
        return self._root / project

    def append(self, entry: ProjectKnowledgeEntry) -> str:
        if not entry.entry_id:
            nums = []
            d = self._dir(entry.project)
            if d.is_dir():
                for f in d.glob(f"{entry.project}-*.md"):
                    m = re.fullmatch(rf"{re.escape(entry.project)}-(\d+)", f.stem)
                    if m:
                        nums.append(int(m.group(1)))
            entry = entry.model_copy(update={"entry_id": f"{entry.project}-{max(nums, default=0) + 1}"})
        path = self._dir(entry.project) / f"{entry.entry_id}.md"
        _write_frontmatter(path, entry.model_dump(mode="json", exclude={"entry_id"}))
        return entry.entry_id

    def list(self, project: str) -> list[ProjectKnowledgeEntry]:
        d = self._dir(project)
        if not d.is_dir():
            return []

        def _num(p: Path) -> int:
            return int(p.stem.rsplit("-", 1)[1])

        entries = []
        for path in sorted(d.glob(f"{project}-*.md"), key=_num):
            meta = _read_frontmatter(path)
            entries.append(ProjectKnowledgeEntry.model_validate({**meta, "entry_id": path.stem}))
        return entries

    def search(self, project: str, query: str) -> list[ProjectKnowledgeEntry]:
        q = query.lower()
        return [
            e for e in self.list(project)
            if q in " ".join([e.statement, e.note]).lower()
        ]



class SqliteKnowledgeBackend:
    """`db_path` のsqliteファイルに案件固有ナレッジを保持する。git管理外(バイナリ)。"""

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    entry_id TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    statement TEXT NOT NULL,
                    source TEXT NOT NULL,
                    retrieved TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def append(self, entry: ProjectKnowledgeEntry) -> str:
        with sqlite3.connect(self._db_path) as con:
            if not entry.entry_id:
                (count,) = con.execute(
                    "SELECT COUNT(*) FROM entries WHERE project = ?", (entry.project,)
                ).fetchone()
                entry = entry.model_copy(update={"entry_id": f"{entry.project}-{count + 1}"})
            con.execute(
                "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?)",
                (entry.entry_id, entry.project, entry.statement, entry.source, entry.retrieved, entry.note),
            )
        return entry.entry_id

    def list(self, project: str) -> list[ProjectKnowledgeEntry]:
        with sqlite3.connect(self._db_path) as con:
            rows = con.execute(
                "SELECT entry_id, project, statement, source, retrieved, note "
                "FROM entries WHERE project = ? ORDER BY entry_id",
                (project,),
            ).fetchall()
        return [
            ProjectKnowledgeEntry(entry_id=r[0], project=r[1], statement=r[2], source=r[3], retrieved=r[4], note=r[5])
            for r in rows
        ]

    def search(self, project: str, query: str) -> list[ProjectKnowledgeEntry]:
        q = query.lower()
        return [
            e for e in self.list(project)
            if q in " ".join([e.statement, e.note]).lower()
        ]


def resolve_knowledge_backend(
    backend: Literal["markdown", "sqlite"], project: str, knowledge_root: Path, medo_home: Path
) -> "KnowledgeBackend":
    if backend == "sqlite":
        return SqliteKnowledgeBackend(Path(medo_home) / "projects" / project / "knowledge.sqlite")
    return MarkdownKnowledgeBackend(Path(knowledge_root) / "projects")
