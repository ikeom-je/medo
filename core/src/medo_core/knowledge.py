"""技術ナレッジ(案件横断)。出典必須・frontmatter付きmdでgit履歴レビュー前提。"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlparse

import sqlite3
import yaml
from pydantic import BaseModel, Field, model_validator

KnowledgeKind = Literal["tech", "market", "policy", "trend", "company", "practice"]
_URL_KINDS = {"tech", "market", "policy", "trend"}
_STALE_THRESHOLD_DAYS = {"tech": 30}
_DEFAULT_STALE_THRESHOLD_DAYS = 180

TrustStatus = Literal["unverified", "machine-confirmed", "human-reviewed"]

# OKF v0.2 の必須フィールドは type だけ。medoのナリッジは1種類なので固定値を書く。
_OKF_TYPE = "knowledge"


def _stale_after(kind: str | None, generated: str) -> str:
    """鮮度契約の期限。LLMに計算させない(原則1)。kind=None は既定の契約。"""
    days = _STALE_THRESHOLD_DAYS.get(kind, _DEFAULT_STALE_THRESHOLD_DAYS)
    return (date.fromisoformat(generated) + timedelta(days=days)).isoformat()


def _from_okf(meta: dict) -> dict:
    """OKF形式と旧形式のどちらのfrontmatterも受ける。

    stale_after はファイルの値を信じない。鮮度契約を変えたとき、保存済みの
    期限が古い契約のまま残る。
    """
    meta = {k: v for k, v in meta.items() if k not in ("type", "stale_after")}
    if "generated" in meta:
        meta["retrieved"] = meta.pop("generated")
    if "sources" in meta and "source" not in meta:
        sources = meta["sources"]
        if isinstance(sources, str):        # 手書きで単数のまま書かれることがある
            meta["source"] = sources
        elif isinstance(sources, list) and sources:
            meta["source"] = str(sources[0])
        else:
            meta["source"] = ""
    meta.pop("sources", None)
    return meta


class SearchResult(BaseModel):
    """打ち切ったことを呼び出し側に見せる。黙って切ると「これで全部」と誤認される。"""

    entries: list = Field(default_factory=list)
    total: int = 0
    truncated: bool = False


DEFAULT_CHAR_BUDGET = 4000


def apply_budget(entries: list, limit: int, char_budget: int) -> SearchResult:
    """件数と文字数の両方で打ち切る。

    件数だけで切ると、1件が長文のときに呼び出し側のコンテキストが破裂する。
    """
    kept: list = []
    used = 0
    for entry in entries:
        if len(kept) >= limit:
            break
        used += len(entry.statement) + len(entry.note)
        if kept and used > char_budget:
            break
        kept.append(entry)
    return SearchResult(entries=kept, total=len(entries), truncated=len(kept) < len(entries))


def body_of(entries: list) -> str:
    return "\n".join(f"- {e.entry_id}: {e.statement[:60]}" for e in entries)


class KnowledgeIndex(BaseModel):
    """何がどれだけあるかの概要。本体を開く前に読む(progressive disclosure)。"""

    scope: str                              # kind名、または案件ID
    entry_count: int
    stale_count: int | None                 # None は鮮度を数えていない層(案件固有)
    generated: str
    body: str = ""


class KnowledgeEntry(BaseModel):
    entry_id: str = ""
    kind: KnowledgeKind
    statement: str
    value: float | None = None
    unit: str = ""
    source: str
    retrieved: str  # ISO日付 YYYY-MM-DD
    status: TrustStatus = "unverified"
    actor: str = ""                       # 書いた主体。人間なら human:<id>
    note: str = ""

    def to_okf(self) -> dict:
        meta = self.model_dump(mode="json", exclude={"entry_id", "source", "retrieved"})
        return {
            "type": _OKF_TYPE, "kind": meta.pop("kind"), "statement": meta.pop("statement"),
            "sources": [self.source], "generated": self.retrieved,
            "stale_after": _stale_after(self.kind, self.retrieved), **meta,
        }

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
        _write_frontmatter(path, entry.to_okf())
        self.rebuild_index(entry.kind)
        return entry.entry_id

    def _entries(self, kind: str) -> list[KnowledgeEntry]:
        d = self._dir(kind)
        if not d.is_dir():
            return []
        return [
            KnowledgeEntry.model_validate(
                {**_from_okf(_read_frontmatter(path)), "entry_id": path.stem, "kind": kind}
            )
            for path in sorted(d.glob(f"{kind}-*.md"))
        ]

    def rebuild_index(self, kind: str, today: date | None = None) -> None:
        """索引を作り直す。stale件数は書かない(読み出し時に数える)。"""
        entries = self._entries(kind)
        body = body_of(entries)
        path = self._dir(kind) / "index.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        front = yaml.safe_dump(
            {"type": "index", "kind": kind, "entry_count": len(entries),
             "generated": (today or date.today()).isoformat()},
            allow_unicode=True, sort_keys=False,
        )
        path.write_text(f"---\n{front}---\n\n## このkindに何があるか\n\n{body}\n", encoding="utf-8")

    def index(self, kind: str, today: date | None = None) -> KnowledgeIndex | None:
        path = self._dir(kind) / "index.md"
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        _, front, body = text.split("---", 2)
        meta = yaml.safe_load(front)
        return KnowledgeIndex(
            scope=kind, entry_count=meta.get("entry_count", 0),
            stale_count=sum(1 for e in self._entries(kind) if e.is_stale(today=today)),
            generated=meta.get("generated", ""), body=body.strip(),
        )

    def kinds(self) -> list[str]:
        if not self._root.is_dir():
            return []
        return sorted(d.name for d in self._root.iterdir() if d.is_dir() and d.name != "projects")

    def get(self, kind: str, entry_id: str) -> KnowledgeEntry | None:
        path = self._dir(kind) / f"{entry_id}.md"
        if not path.exists():
            return None
        meta = _read_frontmatter(path)
        return KnowledgeEntry.model_validate({**_from_okf(meta), "entry_id": entry_id, "kind": kind})

    def search(
        self, query: str = "", kind: str | None = None, limit: int = 10,
        char_budget: int = DEFAULT_CHAR_BUDGET,
    ) -> SearchResult:
        """エントリの実体を走査する。索引は経由しない。

        索引は要約なので、要約に載らなかった語で引くと実体があるのに「無い」と
        返る。取りこぼしは黙って起きるため、呼び出し側から検出できない。
        """
        q = query.lower()
        hits: list[KnowledgeEntry] = []
        for k in [kind] if kind else self.kinds():
            for entry in self._entries(k):
                if q and q not in " ".join([entry.statement, entry.note]).lower():
                    continue
                hits.append(entry)
        return apply_budget(hits, limit, char_budget)


class ProjectKnowledgeEntry(BaseModel):
    entry_id: str = ""
    project: str
    statement: str
    source: str
    retrieved: str
    status: TrustStatus = "unverified"
    actor: str = ""
    note: str = ""

    def to_okf(self) -> dict:
        meta = self.model_dump(mode="json", exclude={"entry_id", "source", "retrieved"})
        return {
            "type": _OKF_TYPE, "project": meta.pop("project"),
            "statement": meta.pop("statement"), "sources": [self.source],
            "generated": self.retrieved,
            "stale_after": _stale_after(None, self.retrieved), **meta,
        }

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

    def index(self, project: str) -> "KnowledgeIndex": ...
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
        _write_frontmatter(path, entry.to_okf())
        self.rebuild_index(entry.project)
        return entry.entry_id

    def rebuild_index(self, project: str, today: date | None = None) -> None:
        entries = self.list(project)
        body = body_of(entries)
        front = yaml.safe_dump(
            {"type": "index", "project": project, "entry_count": len(entries),
             "generated": (today or date.today()).isoformat()},
            allow_unicode=True, sort_keys=False,
        )
        path = self._dir(project) / "index.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{front}---\n\n## この案件に何があるか\n\n{body}\n", encoding="utf-8")

    def index(self, project: str) -> KnowledgeIndex:
        entries = self.list(project)
        path = self._dir(project) / "index.md"
        generated = ""
        if path.exists():
            generated = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1]).get(
                "generated", ""
            )
        return KnowledgeIndex(
            scope=project, entry_count=len(entries), stale_count=None,
            generated=generated, body=body_of(entries),
        )

    def list(self, project: str) -> list[ProjectKnowledgeEntry]:
        d = self._dir(project)
        if not d.is_dir():
            return []

        def _num(p: Path) -> int:
            return int(p.stem.rsplit("-", 1)[1])

        entries = []
        for path in sorted(d.glob(f"{project}-*.md"), key=_num):
            meta = _read_frontmatter(path)
            entries.append(ProjectKnowledgeEntry.model_validate({**_from_okf(meta), "entry_id": path.stem}))
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
                    note TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'unverified',
                    actor TEXT NOT NULL DEFAULT ''
                )
                """
            )
            # 既存DBには新しい列が無い。作り直すと蓄積を捨てることになる。
            existing = {row[1] for row in con.execute("PRAGMA table_info(entries)")}
            for column, default in (("status", "'unverified'"), ("actor", "''")):
                if column not in existing:
                    con.execute(
                        f"ALTER TABLE entries ADD COLUMN {column} TEXT NOT NULL DEFAULT {default}"
                    )

    def append(self, entry: ProjectKnowledgeEntry) -> str:
        with sqlite3.connect(self._db_path) as con:
            if not entry.entry_id:
                (count,) = con.execute(
                    "SELECT COUNT(*) FROM entries WHERE project = ?", (entry.project,)
                ).fetchone()
                entry = entry.model_copy(update={"entry_id": f"{entry.project}-{count + 1}"})
            con.execute(
                "INSERT INTO entries "
                "(entry_id, project, statement, source, retrieved, note, status, actor) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (entry.entry_id, entry.project, entry.statement, entry.source,
                 entry.retrieved, entry.note, entry.status, entry.actor),
            )
        return entry.entry_id

    def list(self, project: str) -> list[ProjectKnowledgeEntry]:
        with sqlite3.connect(self._db_path) as con:
            rows = con.execute(
                "SELECT entry_id, project, statement, source, retrieved, note, status, actor "
                "FROM entries WHERE project = ? ORDER BY entry_id",
                (project,),
            ).fetchall()
        return [
            ProjectKnowledgeEntry(
                entry_id=r[0], project=r[1], statement=r[2], source=r[3],
                retrieved=r[4], note=r[5], status=r[6], actor=r[7],
            )
            for r in rows
        ]

    def search(self, project: str, query: str) -> list[ProjectKnowledgeEntry]:
        q = query.lower()
        return [
            e for e in self.list(project)
            if q in " ".join([e.statement, e.note]).lower()
        ]

    def index(self, project: str) -> KnowledgeIndex:
        """索引ファイルを持たない。バイナリDBに置いてもgitで差分が読めない。"""
        entries = self.list(project)
        return KnowledgeIndex(
            scope=project, entry_count=len(entries), stale_count=None,
            generated=date.today().isoformat(), body=body_of(entries),
        )


def resolve_knowledge_backend(
    backend: Literal["markdown", "sqlite"], project: str, knowledge_root: Path, medo_home: Path
) -> "KnowledgeBackend":
    if backend == "sqlite":
        return SqliteKnowledgeBackend(Path(medo_home) / "projects" / project / "knowledge.sqlite")
    return MarkdownKnowledgeBackend(Path(knowledge_root) / "projects")
