# Knowledge層(技術ナレッジ+案件固有ナレッジ) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GCP専用の`CatalogEntry/CatalogStore`(catalog.py)を廃止し、facts型の技術ナレッジ(案件横断・`knowledge/{kind}/`)と案件固有ナレッジ(単一案件・`knowledge/projects/{id}/`、markdown/sqliteバックエンド選択制)の二層`knowledge.py`に置き換える。CLI・statusの依存箇所も追随させる。

**Architecture:** `knowledge/`はStorage Protocol(JSON)を使わず、独立したmarkdown(frontmatter)ファイル群として`MEDO_HOME/knowledge/`配下(既定で別gitリポジトリ)に直接読み書きする。技術ナレッジ(`KnowledgeEntry`)は`knowledge/{kind}/{entry_id}.md`、案件固有ナレッジ(`ProjectKnowledgeEntry`)は`knowledge/projects/{project_id}/{entry_id}.md`(markdownバックエンド既定)または`MEDO_HOME/projects/{id}/knowledge.sqlite`(sqliteバックエンド)に保存する。バックエンド選択は`RequirementsDoc.knowledge_backend`に持たせる。

**Tech Stack:** Python 3.12 / pydantic >= 2.7 / PyYAML(frontmatter) / sqlite3(標準ライブラリ) / typer / pytest

## Global Constraints

- Python 3.12+、pydantic >= 2.7、pytest >= 8、ruff(line-length 100)
- 出典なしのファクト・技術ナレッジはバリデーション拒否(`.claude/steering/product.md` 原則5)
- CLIは失敗時に非ゼロ終了+`error: <理由>`(stderr)、推測で補完しない
- テストは`tmp_path`で完結させる(実ファイルシステム外部依存なし)。日付依存テストは`today`引数注入で固定する
- コミットメッセージは日本語Conventional Commits(`.claude/steering/git.md`)

---

### Task 1: `KnowledgeEntry` + `KnowledgeStore`(案件横断・catalog.py置き換え)

**Files:**
- Create: `core/src/medo_core/knowledge.py`
- Test: `core/tests/test_knowledge.py`
- Delete: `core/src/medo_core/catalog.py`, `core/tests/test_catalog.py`

**Interfaces:**
- Produces: `KnowledgeEntry(entry_id: str = "", kind: Literal["tech","market","policy","trend","company"], statement: str, value: float | None, unit: str, source: str, retrieved: str, note: str)`, `KnowledgeEntry.is_stale(today: date | None = None) -> bool`(kind別閾値: `tech`=30日、他=180日)、`KnowledgeStore(root: Path)` with `save(entry) -> str`, `get(kind, entry_id) -> KnowledgeEntry | None`, `search(query="", kind=None, limit=10) -> list[KnowledgeEntry]`

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_knowledge.py
from datetime import date
from pathlib import Path

import pytest

from medo_core.knowledge import KnowledgeEntry, KnowledgeStore


def _entry(**kw) -> KnowledgeEntry:
    base = dict(
        kind="tech",
        statement="Vertex AI context caching は 2026年時点でGA",
        source="https://cloud.google.com/vertex-ai/docs/context-cache",
        retrieved="2026-07-01",
    )
    base.update(kw)
    return KnowledgeEntry(**base)


@pytest.fixture
def store(tmp_path: Path) -> KnowledgeStore:
    return KnowledgeStore(tmp_path)


def test_save_assigns_entry_id_and_get_roundtrips(store: KnowledgeStore):
    entry_id = store.save(_entry())
    assert entry_id == "tech-1"
    got = store.get("tech", entry_id)
    assert got.statement == "Vertex AI context caching は 2026年時点でGA"
    assert got.source.startswith("https://")


def test_save_increments_entry_id_per_kind(store: KnowledgeStore):
    store.save(_entry())
    second = store.save(_entry(statement="second"))
    assert second == "tech-2"


def test_source_required():
    with pytest.raises(ValueError):
        _entry(source="")


def test_tech_kind_requires_url_source():
    with pytest.raises(ValueError):
        _entry(source="社内メモ")


def test_company_kind_allows_non_url_source():
    entry = _entry(kind="company", source="決算説明資料 2026Q2")
    assert entry.source == "決算説明資料 2026Q2"


def test_is_stale_tech_threshold_30_days():
    entry = _entry(retrieved="2026-01-01")
    assert entry.is_stale(today=date(2026, 3, 1)) is True
    assert entry.is_stale(today=date(2026, 1, 15)) is False


def test_is_stale_market_threshold_180_days():
    entry = _entry(kind="market", source="https://example.com/report", retrieved="2026-01-01")
    assert entry.is_stale(today=date(2026, 5, 1)) is False
    assert entry.is_stale(today=date(2026, 8, 1)) is True


def test_search_matches_statement_and_note(store: KnowledgeStore):
    store.save(_entry(statement="Gemini Flash pricing"))
    store.save(_entry(statement="unrelated", note="context caching detail"))
    results = store.search("caching")
    assert len(results) == 2


def test_search_filters_by_kind(store: KnowledgeStore):
    store.save(_entry(kind="tech"))
    store.save(_entry(kind="company", source="社内資料", statement="社内メモ"))
    results = store.search(kind="company")
    assert len(results) == 1
    assert results[0].kind == "company"


def test_get_missing_returns_none(store: KnowledgeStore):
    assert store.get("tech", "tech-999") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest core/tests/test_knowledge.py -v`
Expected: FAIL(`ModuleNotFoundError: medo_core.knowledge`)

- [ ] **Step 3: Write minimal implementation**

```python
# core/src/medo_core/knowledge.py
"""技術ナレッジ(案件横断)。出典必須・frontmatter付きmdでgit履歴レビュー前提。"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest core/tests/test_knowledge.py -v`
Expected: PASS(10 tests)

- [ ] **Step 5: Delete catalog.py and its test**

```bash
git rm core/src/medo_core/catalog.py core/tests/test_catalog.py
```

- [ ] **Step 6: Run full core test suite**

Run: `uv run pytest core/tests -v`
Expected: PASS(catalog参照が残っていないこと。まだ`status.py`/`main.py`がcatalogをimportしているためこの時点ではPASSしない場合がある — Task 4・5で解消する。ここでは`test_knowledge.py`と無関係の既存テストが壊れていないことのみ確認する)

- [ ] **Step 7: Commit**

```bash
git add core/src/medo_core/knowledge.py core/tests/test_knowledge.py
git commit -m "feat(core): 技術ナレッジ(KnowledgeEntry+KnowledgeStore)でcatalogを置き換え"
```

---

### Task 2: `ProjectKnowledgeEntry` + `KnowledgeBackend`(markdown実装)

**Files:**
- Modify: `core/src/medo_core/knowledge.py`
- Test: `core/tests/test_knowledge.py`(追記)

**Interfaces:**
- Consumes: Task 1の`_write_frontmatter` / `_read_frontmatter`
- Produces: `ProjectKnowledgeEntry(entry_id: str = "", project: str, statement: str, source: str, retrieved: str, note: str = "")`、`KnowledgeBackend` Protocol(`append(entry) -> str`, `list(project) -> list[ProjectKnowledgeEntry]`, `search(project, query) -> list[ProjectKnowledgeEntry]`)、`MarkdownKnowledgeBackend(root: Path)`(root = `knowledge/projects`)

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_knowledge.py に追記
from medo_core.knowledge import MarkdownKnowledgeBackend, ProjectKnowledgeEntry


def _project_entry(**kw) -> ProjectKnowledgeEntry:
    base = dict(
        project="yoyaku",
        statement="顧客の予約システムは現在Excel管理。現場担当者はPC操作に不慣れ",
        source="hearing Skill 2026-07-27対話",
        retrieved="2026-07-27",
    )
    base.update(kw)
    return ProjectKnowledgeEntry(**base)


@pytest.fixture
def md_backend(tmp_path: Path) -> MarkdownKnowledgeBackend:
    return MarkdownKnowledgeBackend(tmp_path / "projects")


def test_append_assigns_entry_id(md_backend: MarkdownKnowledgeBackend):
    entry_id = md_backend.append(_project_entry())
    assert entry_id == "yoyaku-1"


def test_append_increments_per_project(md_backend: MarkdownKnowledgeBackend):
    md_backend.append(_project_entry())
    second = md_backend.append(_project_entry(statement="second"))
    assert second == "yoyaku-2"


def test_list_returns_saved_entries(md_backend: MarkdownKnowledgeBackend):
    md_backend.append(_project_entry())
    md_backend.append(_project_entry(statement="second"))
    entries = md_backend.list("yoyaku")
    assert [e.statement for e in entries] == [
        "顧客の予約システムは現在Excel管理。現場担当者はPC操作に不慣れ",
        "second",
    ]


def test_list_scoped_to_project(md_backend: MarkdownKnowledgeBackend):
    md_backend.append(_project_entry(project="yoyaku"))
    md_backend.append(_project_entry(project="other"))
    assert len(md_backend.list("yoyaku")) == 1


def test_search_matches_statement(md_backend: MarkdownKnowledgeBackend):
    md_backend.append(_project_entry(statement="Excel管理からの脱却"))
    md_backend.append(_project_entry(statement="無関係な話題"))
    results = md_backend.search("yoyaku", "Excel")
    assert len(results) == 1


def test_source_and_statement_required():
    with pytest.raises(ValueError):
        ProjectKnowledgeEntry(project="yoyaku", statement="", source="hearing対話", retrieved="2026-07-27")
    with pytest.raises(ValueError):
        ProjectKnowledgeEntry(project="yoyaku", statement="x", source="", retrieved="2026-07-27")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest core/tests/test_knowledge.py -v`
Expected: FAIL(`ImportError: cannot import name 'MarkdownKnowledgeBackend'`)

- [ ] **Step 3: Write minimal implementation**

```python
# core/src/medo_core/knowledge.py に追記
from typing import Protocol


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest core/tests/test_knowledge.py -v`
Expected: PASS(全テスト)

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/knowledge.py core/tests/test_knowledge.py
git commit -m "feat(core): 案件固有ナレッジ(ProjectKnowledgeEntry+MarkdownKnowledgeBackend)を追加"
```

---

### Task 3: `SqliteKnowledgeBackend`

**Files:**
- Modify: `core/src/medo_core/knowledge.py`
- Test: `core/tests/test_knowledge.py`(追記)

**Interfaces:**
- Consumes: Task 2の`ProjectKnowledgeEntry`・`KnowledgeBackend` Protocol
- Produces: `SqliteKnowledgeBackend(db_path: Path)`(同じProtocolを満たす)

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_knowledge.py に追記
from medo_core.knowledge import SqliteKnowledgeBackend


@pytest.fixture
def sqlite_backend(tmp_path: Path) -> SqliteKnowledgeBackend:
    return SqliteKnowledgeBackend(tmp_path / "knowledge.sqlite")


def test_sqlite_append_and_list_roundtrip(sqlite_backend: SqliteKnowledgeBackend):
    sqlite_backend.append(_project_entry())
    sqlite_backend.append(_project_entry(statement="second"))
    entries = sqlite_backend.list("yoyaku")
    assert [e.statement for e in entries] == [
        "顧客の予約システムは現在Excel管理。現場担当者はPC操作に不慣れ",
        "second",
    ]


def test_sqlite_search_matches_statement(sqlite_backend: SqliteKnowledgeBackend):
    sqlite_backend.append(_project_entry(statement="Excel管理からの脱却"))
    sqlite_backend.append(_project_entry(statement="無関係"))
    results = sqlite_backend.search("yoyaku", "Excel")
    assert len(results) == 1


def test_sqlite_scoped_to_project(sqlite_backend: SqliteKnowledgeBackend):
    sqlite_backend.append(_project_entry(project="yoyaku"))
    sqlite_backend.append(_project_entry(project="other"))
    assert len(sqlite_backend.list("yoyaku")) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest core/tests/test_knowledge.py -v`
Expected: FAIL(`ImportError: cannot import name 'SqliteKnowledgeBackend'`)

- [ ] **Step 3: Write minimal implementation**

```python
# core/src/medo_core/knowledge.py に追記
import sqlite3


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
```

`entry_id`のソートは文字列順のため`entries`が10件を超えると`project-10`が`project-2`より前に来る点に注意(Markdown側も同じ制約はTask2の`_num`ソートで回避済み。sqlite側は`ORDER BY entry_id`が文字列順である点を許容する — 案件固有ナレッジはフェーズ1で数百件規模を想定しないため許容範囲とする)。

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest core/tests/test_knowledge.py -v`
Expected: PASS(全テスト)

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/knowledge.py core/tests/test_knowledge.py
git commit -m "feat(core): 案件固有ナレッジのSqliteKnowledgeBackendを追加"
```

---

### Task 4: `RequirementsDoc.knowledge_backend` + バックエンド選択関数

**Files:**
- Modify: `core/src/medo_core/requirements.py`
- Modify: `core/src/medo_core/knowledge.py`
- Test: `core/tests/test_requirements.py`(既存ファイルに追記)、`core/tests/test_knowledge.py`(追記)

**Interfaces:**
- Consumes: `RequirementsDoc`(requirements.py)、`MarkdownKnowledgeBackend` / `SqliteKnowledgeBackend`(knowledge.py)
- Produces: `RequirementsDoc.knowledge_backend: Literal["markdown", "sqlite"] = "markdown"`、`resolve_knowledge_backend(backend: str, project: str, knowledge_root: Path, medo_home: Path) -> KnowledgeBackend`

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_requirements.py に追記(既存の import 群はそのまま利用)
def test_knowledge_backend_defaults_to_markdown():
    doc = RequirementsDoc(project="yoyaku")
    assert doc.knowledge_backend == "markdown"


def test_knowledge_backend_accepts_sqlite():
    doc = RequirementsDoc(project="yoyaku", knowledge_backend="sqlite")
    assert doc.knowledge_backend == "sqlite"
```

```python
# core/tests/test_knowledge.py に追記
from medo_core.knowledge import resolve_knowledge_backend


def test_resolve_knowledge_backend_markdown(tmp_path: Path):
    backend = resolve_knowledge_backend("markdown", "yoyaku", tmp_path / "knowledge", tmp_path / "home")
    assert isinstance(backend, MarkdownKnowledgeBackend)


def test_resolve_knowledge_backend_sqlite(tmp_path: Path):
    backend = resolve_knowledge_backend("sqlite", "yoyaku", tmp_path / "knowledge", tmp_path / "home")
    assert isinstance(backend, SqliteKnowledgeBackend)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest core/tests/test_requirements.py core/tests/test_knowledge.py -v`
Expected: FAIL(`knowledge_backend`未定義のvalidation error / `ImportError: resolve_knowledge_backend`)

- [ ] **Step 3: Write minimal implementation**

```python
# core/src/medo_core/requirements.py: RequirementsDoc に1行追加
class RequirementsDoc(BaseModel):
    project: str
    version: int = 1
    industry: str = ""
    background: str = ""
    goal: str = ""
    principles: list[ConfidenceItem] = Field(default_factory=list)
    challenges: list[ConfidenceItem] = Field(default_factory=list)
    functional: list[FunctionalRequirement] = Field(default_factory=list)
    non_functional: dict[str, str] = Field(default_factory=dict)
    open_questions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    knowledge_backend: Literal["markdown", "sqlite"] = "markdown"
```

```python
# core/src/medo_core/knowledge.py に追記
def resolve_knowledge_backend(
    backend: Literal["markdown", "sqlite"], project: str, knowledge_root: Path, medo_home: Path
) -> "KnowledgeBackend":
    if backend == "sqlite":
        return SqliteKnowledgeBackend(Path(medo_home) / "projects" / project / "knowledge.sqlite")
    return MarkdownKnowledgeBackend(Path(knowledge_root) / "projects")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest core/tests/test_requirements.py core/tests/test_knowledge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/requirements.py core/src/medo_core/knowledge.py core/tests/test_requirements.py core/tests/test_knowledge.py
git commit -m "feat(core): 案件ごとのknowledge_backend選択(markdown|sqlite)を追加"
```

---

### Task 5: `Artifact.cited_catalog_entries` → `cited_knowledge` リネーム

**Files:**
- Modify: `core/src/medo_core/artifacts.py`
- Modify: `core/tests/test_artifacts.py`(既存の`cited_catalog_entries`参照を置換)

**Interfaces:**
- Produces: `Artifact.cited_knowledge: list[str]`(旧`cited_catalog_entries`を置き換え。フィールド名変更のみ、意味は同じ=引用した技術ナレッジのentry_id一覧)

- [ ] **Step 1: 既存テストのフィールド名を置換**

```bash
grep -rl "cited_catalog_entries" core/tests/ cli/
```
出てきた箇所すべてで `cited_catalog_entries` → `cited_knowledge` に置換する(sedではなくEditツールで1箇所ずつ確認しながら置換。挙動を変えない機械的リネームのため新規テストは書かない)。

- [ ] **Step 2: 実装を置換**

```python
# core/src/medo_core/artifacts.py
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
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest core/tests/test_artifacts.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add core/src/medo_core/artifacts.py core/tests/test_artifacts.py
git commit -m "refactor(core): Artifact.cited_catalog_entries を cited_knowledge にリネーム"
```

---

### Task 6: `medo status` を knowledge 版に差し替え(Issue #29)

**Files:**
- Modify: `core/src/medo_core/status.py`
- Test: `core/tests/test_status.py`(既存の`CatalogStore`/`CatalogEntry`関連fixtureを`KnowledgeStore`/`KnowledgeEntry`に置換)

**Interfaces:**
- Consumes: `KnowledgeStore`(Task 1)、`Artifact.cited_knowledge`(Task 5)
- Produces: `_knowledge_entry_stale(store: KnowledgeStore, entry_id: str, today: date | None) -> bool`(旧`_catalog_entry_stale`を置き換え)

- [ ] **Step 1: 既存テストの参照を置換**

`core/tests/test_status.py`内の`CatalogStore`/`CatalogEntry`/`cited_catalog_entries`を、Task1の`KnowledgeStore`/`KnowledgeEntry`(`kind="tech"`固定でよい)/Task5の`cited_knowledge`に置換する。`KnowledgeStore`のコンストラクタは`Storage`ではなく`Path`(tmp_path配下の`knowledge`ディレクトリ)を受け取る点に注意。

```python
# 置換後のfixture例
@pytest.fixture
def knowledge_store(tmp_path: Path) -> KnowledgeStore:
    return KnowledgeStore(tmp_path / "knowledge")
```
テスト内で`project_status(storage, ...)`を呼ぶ際、`knowledge_store`のrootを渡す経路が必要になるため、Step 3の実装変更に合わせて`project_status`のシグネチャに`knowledge_root: Path`を追加する(下記実装参照)。既存呼び出し箇所(テスト・CLI)も合わせて更新する。

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest core/tests/test_status.py -v`
Expected: FAIL(`ImportError: cannot import name 'CatalogStore'` 等)

- [ ] **Step 3: Write minimal implementation**

```python
# core/src/medo_core/status.py
from __future__ import annotations

from datetime import date
from pathlib import Path

from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.facts import Fact, FactStore
from medo_core.knowledge import KnowledgeStore
from medo_core.requirements import RequirementsStore
from medo_core.storage import Storage


def _knowledge_entry_stale(store: KnowledgeStore, entry_id: str, today: date | None) -> bool:
    """引用ナレッジエントリがstaleまたは欠落ならTrue。"""
    if "-" not in entry_id:
        return True
    kind, _ = entry_id.rsplit("-", 1)
    entry = store.get(kind, entry_id)
    return entry is None or entry.is_stale(today=today)


def _artifact_stale(
    artifact: Artifact,
    current_version: int,
    facts_by_id: dict[str, Fact],
    knowledge_store: KnowledgeStore,
    today: date | None,
) -> bool:
    if artifact.requirements_version < current_version:
        return True
    for fact_id in artifact.cited_facts:
        fact = facts_by_id.get(fact_id)
        if fact is None or fact.is_stale(today=today):
            return True
    return any(
        _knowledge_entry_stale(knowledge_store, entry_id, today)
        for entry_id in artifact.cited_knowledge
    )


def project_status(
    storage: Storage, project_id: str, knowledge_root: Path, today: date | None = None
) -> dict:
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
    knowledge_store = KnowledgeStore(knowledge_root)

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
            "stale": _artifact_stale(a, version, facts_by_id, knowledge_store, today),
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


def stale_artifact_ids(
    storage: Storage, project_id: str, knowledge_root: Path, today: date | None = None
) -> list[str]:
    report = project_status(storage, project_id, knowledge_root, today=today)
    return [row["id"] for row in report["artifacts"] if row["stale"]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest core/tests/test_status.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/status.py core/tests/test_status.py
git commit -m "feat(core): medo status の陳腐化判定をknowledge版に差し替え"
```

---

### Task 7: CLI: `catalog` → `knowledge`(Issue #28)

**Files:**
- Modify: `cli/src/medo_cli/main.py`
- Modify: `core/src/medo_core/config.py`(knowledgeルート解決を追加)
- Test: `cli/tests/test_cli.py`(既存の`catalog`関連テストを`knowledge`に置換・`--project`付き案件固有ナレッジのテストを追加)

**Interfaces:**
- Consumes: `KnowledgeStore` / `resolve_knowledge_backend`(core/knowledge.py)、`RequirementsStore.get`(knowledge_backend参照用)
- Produces: `get_knowledge_root() -> Path`(config.py)、CLI `medo knowledge search|save|get`(`--project`の有無で案件横断/案件固有を切替)

- [ ] **Step 1: config.pyに knowledge ルート解決を追加**

```python
# core/src/medo_core/config.py に追記
def get_knowledge_root() -> Path:
    return Path(os.environ.get("MEDO_HOME", str(Path.home() / ".medo"))) / "knowledge"
```

- [ ] **Step 2: 既存CLIテストの catalog 関連を置換**

`cli/tests/test_cli.py`内の`catalog search`/`catalog get`呼び出しを`knowledge search`/`knowledge get --kind ...`に置換する。

- [ ] **Step 3: Write the failing test(案件固有ナレッジの新規テスト)**

```python
# cli/tests/test_cli.py に追記
def test_knowledge_save_project_scope_and_search(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDO_HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "knowledge", "save",
            "--project", "yoyaku",
            "--statement", "顧客の予約システムは現在Excel管理",
            "--source", "hearing Skill 2026-07-27対話",
        ],
    )
    assert result.exit_code == 0
    assert "saved: yoyaku-1" in result.stdout

    search = runner.invoke(app, ["knowledge", "search", "Excel", "--project", "yoyaku"])
    assert search.exit_code == 0
    assert "yoyaku-1" in search.stdout


def test_knowledge_save_project_scope_rejects_missing_source(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDO_HOME", str(tmp_path))
    result = runner.invoke(
        app, ["knowledge", "save", "--project", "yoyaku", "--statement", "x", "--source", ""]
    )
    assert result.exit_code == 1
    assert "error:" in result.stdout + result.stderr
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest cli/tests/test_cli.py -v`
Expected: FAIL(`knowledge`コマンド未実装)

- [ ] **Step 5: Write minimal implementation**

```python
# cli/src/medo_cli/main.py の catalog 関連(import・catalog_app・catalog_search・catalog_get)を削除し、以下に置き換え

from medo_core.config import get_knowledge_root, get_storage
from medo_core.knowledge import KnowledgeEntry, KnowledgeStore, ProjectKnowledgeEntry, resolve_knowledge_backend
from medo_core.requirements import RequirementsStore

knowledge_app = typer.Typer(no_args_is_help=True)
app.add_typer(knowledge_app, name="knowledge", help="技術ナレッジ(案件横断)/ 案件固有ナレッジ")


def _knowledge_entry_payload(entry) -> dict:
    return {"entry": entry.model_dump(mode="json"), "stale": entry.is_stale()} if hasattr(entry, "is_stale") else entry.model_dump(mode="json")


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(""),
    project: str | None = typer.Option(None, help="指定時は案件固有ナレッジを検索"),
    kind: str | None = typer.Option(None, help="tech|market|policy|trend|company(案件横断のみ)"),
    format: Literal["json", "digest"] = typer.Option("digest"),
):
    if project:
        storage = get_storage()
        doc = RequirementsStore(storage).get(project)
        backend_name = doc.knowledge_backend if doc else "markdown"
        backend = resolve_knowledge_backend(
            backend_name, project, get_knowledge_root(), Path(os.environ.get("MEDO_HOME", str(Path.home() / ".medo")))
        )
        entries = backend.search(project, query)
        if format == "json":
            typer.echo(json.dumps([e.model_dump(mode="json") for e in entries], ensure_ascii=False, indent=2))
            return
        if not entries:
            typer.echo("(該当なし)")
            return
        for e in entries:
            typer.echo(f"{e.entry_id} {e.statement[:60]} (出典: {e.source}, {e.retrieved})")
        return

    entries = KnowledgeStore(get_knowledge_root()).search(query, kind=kind)
    if format == "json":
        typer.echo(json.dumps([_knowledge_entry_payload(e) for e in entries], ensure_ascii=False, indent=2))
        return
    if not entries:
        typer.echo("(該当なし)")
        return
    for e in entries:
        stale = " [STALE]" if e.is_stale() else ""
        typer.echo(f"{e.entry_id} [{e.kind}]{stale} {e.statement[:60]}")


@knowledge_app.command("get")
def knowledge_get(
    kind: str = typer.Option(..., help="tech|market|policy|trend|company"),
    id: str = typer.Option(..., "--id"),
    format: Literal["json", "digest"] = typer.Option("json"),
):
    entry = KnowledgeStore(get_knowledge_root()).get(kind, id)
    if entry is None:
        _fail(f"ナレッジに {kind}/{id} が見つかりません")
    if format == "json":
        typer.echo(json.dumps(_knowledge_entry_payload(entry), ensure_ascii=False, indent=2))
        return
    stale = " [STALE]" if entry.is_stale() else ""
    typer.echo(f"{entry.entry_id}{stale} {entry.statement[:60]}")


@knowledge_app.command("save")
def knowledge_save(
    statement: str = typer.Option(...),
    source: str = typer.Option(...),
    project: str | None = typer.Option(None, help="指定時は案件固有ナレッジとして保存"),
    kind: str | None = typer.Option(None, help="案件横断ナレッジのみ必須: tech|market|policy|trend|company"),
    value: float | None = typer.Option(None),
    unit: str = typer.Option(""),
    retrieved: str | None = typer.Option(None, help="取得日 YYYY-MM-DD(省略時は今日)"),
    note: str = typer.Option(""),
):
    retrieved = retrieved or date.today().isoformat()
    if project:
        try:
            entry = ProjectKnowledgeEntry(project=project, statement=statement, source=source, retrieved=retrieved, note=note)
        except Exception as e:
            _fail(f"案件固有ナレッジのスキーマ不正: {e}")
        storage = get_storage()
        doc = RequirementsStore(storage).get(project)
        backend_name = doc.knowledge_backend if doc else "markdown"
        backend = resolve_knowledge_backend(
            backend_name, project, get_knowledge_root(), Path(os.environ.get("MEDO_HOME", str(Path.home() / ".medo")))
        )
        entry_id = backend.append(entry)
        typer.echo(f"saved: {entry_id}")
        return

    if not kind:
        _fail("--project 未指定の場合は --kind が必須です")
    try:
        entry = KnowledgeEntry(kind=kind, statement=statement, value=value, unit=unit, source=source, retrieved=retrieved, note=note)
    except Exception as e:
        _fail(f"ナレッジのスキーマ不正: {e}")
    entry_id = KnowledgeStore(get_knowledge_root()).save(entry)
    typer.echo(f"saved: {entry_id}")
```

`app`定義部の`catalog_app`関連行(`catalog_app = typer.Typer(...)`, `app.add_typer(catalog_app, ...)`)は削除する。`main.py`冒頭の`import os`が無ければ追加する。`_entry_payload`は`knowledge`用途に統合したため削除してよい(重複関数を残さない)。

- [ ] **Step 6: statusコマンドのknowledge_root引数を配線**

```python
# cli/src/medo_cli/main.py の status コマンドを修正
@app.command()
def status(project: str = typer.Option(...)):
    """プロジェクトの現在地(要件・ファクト・生成物・next_step)をJSONで出力する。"""
    report = project_status(get_storage(), project, get_knowledge_root())
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
```
`requirements_diff`内の`stale_artifact_ids(storage, project)`呼び出しにも`get_knowledge_root()`を追加する。

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest cli/tests -v`
Expected: PASS

- [ ] **Step 8: Run full test suite + lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 全パッケージPASS、リント違反なし

- [ ] **Step 9: Commit**

```bash
git add cli/src/medo_cli/main.py core/src/medo_core/config.py cli/tests/test_cli.py
git commit -m "feat(cli): catalogコマンドをknowledge(案件横断/案件固有)に置き換え"
```

---

### Task 8: 実装計画本体(medo-phase1.md)の同期(Issue #26)

**Files:**
- Modify: `docs/superpowers/plans/medo-phase1.md`

**Interfaces:** なし(ドキュメントのみ)

- [ ] **Step 1: catalog/etl前提の記述を置換**

以下を一括で見直す(grep結果は本Issue着手時に`grep -n -i "catalog\|etl" docs/superpowers/plans/medo-phase1.md`で再取得すること):
- Goal節の「GCPカタログ根拠付き」→「技術ナレッジ根拠付き」
- ディレクトリ構造図の`catalog.py`→`knowledge.py`、`etl/`パッケージ一式を削除
- `pyproject.toml`の`members = ["core", "cli", "etl"]`→`["core", "cli"]`、`testpaths`から`etl/tests`を削除
- 「Task 4: カタログ」節を本Plan(`2026-07-30-knowledge-layer.md`)のTask1-3への参照に置き換え、旧`CatalogEntry`/`CatalogStore`のコード例を削除
- Task 7(ETL)・Task 8(SKUスナップショット)は、Issue #31(Task8要否再検討の結論)を待って削除または`knowledge save`手動フローに置き換える

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/medo-phase1.md
git commit -m "docs: 実装計画をknowledge層設計に同期"
```

---

## Self-Review Notes

- **Spec coverage**: 二層構成(Task1/2/3)、backend選択(Task4)、CLI `--project`分岐(Task7)、status陳腐化判定(Task6)、生成物の`cited_knowledge`リネーム(Task5)、計画書同期(Task8)を網羅
- **既存Issue対応**: #27→Task1-6、#28→Task7、#29→Task6、#26→Task8
- **未対応のまま残すもの**: 外部連携(Obsidian/Notion)はフェーズ2としてこの計画に含めない。Issue #31(Task8 ETL要否)は本計画の対象外(別途判断)
