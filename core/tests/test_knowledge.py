from datetime import date
from pathlib import Path

import pytest
import yaml

from medo_core.knowledge import (
    KnowledgeEntry,
    KnowledgeStore,
    MarkdownKnowledgeBackend,
    ProjectKnowledgeEntry,
    SqliteKnowledgeBackend,
    resolve_knowledge_backend,
)


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
    assert len(results) == 1


def test_search_filters_by_kind(store: KnowledgeStore):
    store.save(_entry(kind="tech"))
    store.save(_entry(kind="company", source="社内資料", statement="社内メモ"))
    results = store.search(kind="company")
    assert len(results) == 1
    assert results[0].kind == "company"


def test_get_missing_returns_none(store: KnowledgeStore):
    assert store.get("tech", "tech-999") is None




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




def test_resolve_knowledge_backend_markdown(tmp_path: Path):
    backend = resolve_knowledge_backend("markdown", "yoyaku", tmp_path / "knowledge", tmp_path / "home")
    assert isinstance(backend, MarkdownKnowledgeBackend)


def test_resolve_knowledge_backend_sqlite(tmp_path: Path):
    backend = resolve_knowledge_backend("sqlite", "yoyaku", tmp_path / "knowledge", tmp_path / "home")
    assert isinstance(backend, SqliteKnowledgeBackend)


def test_saved_frontmatter_is_okf(store: KnowledgeStore, tmp_path: Path):
    """OKFの必須フィールドは type。他のツールが読める形で置く。"""
    entry_id = store.save(_entry())
    meta = yaml.safe_load(
        (tmp_path / "tech" / f"{entry_id}.md").read_text(encoding="utf-8").split("---")[1]
    )

    assert meta["type"] == "knowledge"
    assert meta["sources"] == ["https://cloud.google.com/vertex-ai/docs/context-cache"]
    assert meta["generated"] == "2026-07-01"
    assert meta["status"] == "unverified"


def test_stale_after_is_derived_from_the_freshness_contract(store: KnowledgeStore, tmp_path: Path):
    """期限をLLMに計算させない。techは30日、それ以外は180日。"""
    store.save(_entry())
    store.save(_entry(kind="market", source="https://example.com/m", retrieved="2026-07-01"))

    def _stale_after(kind, entry_id):
        text = (tmp_path / kind / f"{entry_id}.md").read_text(encoding="utf-8")
        return yaml.safe_load(text.split("---")[1])["stale_after"]

    assert _stale_after("tech", "tech-1") == "2026-07-31"
    assert _stale_after("market", "market-1") == "2026-12-28"


def test_reads_entries_saved_before_okf(store: KnowledgeStore, tmp_path: Path):
    """旧形式のファイルを読めなくしない。"""
    path = tmp_path / "tech" / "tech-9.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nkind: tech\nstatement: 旧形式\nsource: https://example.com/old\n"
        "retrieved: '2026-07-01'\nnote: ''\n---\n",
        encoding="utf-8",
    )

    entry = store.get("tech", "tech-9")

    assert entry.source == "https://example.com/old"
    assert entry.retrieved == "2026-07-01"
    assert entry.status == "unverified"


def test_stale_after_in_the_file_is_not_trusted(store: KnowledgeStore, tmp_path: Path):
    """鮮度契約を変えたとき、保存済みの期限が古い契約のまま残る。"""
    path = tmp_path / "tech" / "tech-9.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntype: knowledge\nkind: tech\nstatement: 期限が嘘\n"
        "sources:\n- https://example.com/x\ngenerated: '2026-07-01'\n"
        "stale_after: '2099-01-01'\n---\n",
        encoding="utf-8",
    )

    assert store.get("tech", "tech-9").is_stale(today=date(2026, 8, 15)) is True


def test_practice_kind_takes_a_non_url_source():
    """レビューや対話で得たノウハウには引けるURLが無い。出典の形式だけを緩める。"""
    entry = _entry(kind="practice", source="medo-review 2026-09-23対話")

    assert entry.kind == "practice"


def test_practice_kind_still_requires_a_source():
    with pytest.raises(ValueError):
        _entry(kind="practice", source="   ")
