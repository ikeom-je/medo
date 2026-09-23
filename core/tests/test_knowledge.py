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
    result = store.search("caching")
    assert result.total == 1


def test_search_filters_by_kind(store: KnowledgeStore):
    store.save(_entry(kind="tech"))
    store.save(_entry(kind="company", source="社内資料", statement="社内メモ"))
    result = store.search(kind="company")
    assert result.total == 1
    assert result.entries[0].kind == "company"


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


def test_sources_written_as_a_bare_string_is_read_whole(store: KnowledgeStore, tmp_path: Path):
    """手書きで単数のまま書かれても、先頭1文字を出典と誤読しない。"""
    path = tmp_path / "tech" / "tech-9.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\ntype: knowledge\nkind: tech\nstatement: 単数で書かれた\n"
        "sources: https://example.com/x\ngenerated: '2026-07-01'\n---\n",
        encoding="utf-8",
    )

    assert store.get("tech", "tech-9").source == "https://example.com/x"


def test_project_entry_roundtrips_through_okf(md_backend: MarkdownKnowledgeBackend, tmp_path: Path):
    """案件固有ナレッジも同じ形式で置く。バックエンドごとに形が変わると読み手が困る。"""
    md_backend.append(ProjectKnowledgeEntry(
        project="p1", statement="紙の伝票が残っている",
        source="ヒアリング(2026-09-23 営業部長)", retrieved="2026-09-23", actor="claude-opus-5",
    ))
    meta = yaml.safe_load(
        (tmp_path / "projects" / "p1" / "p1-1.md").read_text(encoding="utf-8").split("---")[1]
    )

    assert meta["type"] == "knowledge"
    assert meta["sources"] == ["ヒアリング(2026-09-23 営業部長)"]
    assert md_backend.list("p1")[0].actor == "claude-opus-5"


def test_sqlite_keeps_status_and_actor(sqlite_backend: SqliteKnowledgeBackend):
    """markdown と sqlite で残るフィールドが食い違うと、バックエンド変更で情報が消える。"""
    sqlite_backend.append(ProjectKnowledgeEntry(
        project="p1", statement="紙の伝票が残っている", source="ヒアリング(2026-09-23)",
        retrieved="2026-09-23", status="human-reviewed", actor="human:ikeo",
    ))

    entry = sqlite_backend.list("p1")[0]

    assert (entry.status, entry.actor) == ("human-reviewed", "human:ikeo")


def test_sqlite_opens_a_database_created_before_status_and_actor(tmp_path: Path):
    """作り直すと蓄積を捨てることになる。既存DBは列を足して開き続ける。"""
    import sqlite3

    db = tmp_path / "old.sqlite"
    with sqlite3.connect(db) as con:
        con.execute(
            "CREATE TABLE entries (entry_id TEXT PRIMARY KEY, project TEXT NOT NULL, "
            "statement TEXT NOT NULL, source TEXT NOT NULL, retrieved TEXT NOT NULL, "
            "note TEXT NOT NULL DEFAULT '')"
        )
        con.execute("INSERT INTO entries VALUES ('p1-1','p1','古い行','メモ','2026-07-01','')")

    entry = SqliteKnowledgeBackend(db).list("p1")[0]

    assert (entry.statement, entry.status) == ("古い行", "unverified")


def test_index_counts_entries_and_is_written_as_okf(store: KnowledgeStore, tmp_path: Path):
    store.save(_entry())
    store.save(_entry(statement="second"))
    meta = yaml.safe_load(
        (tmp_path / "tech" / "index.md").read_text(encoding="utf-8").split("---")[1]
    )

    assert meta["type"] == "index"
    assert meta["entry_count"] == 2


def test_index_counts_stale_at_read_time(store: KnowledgeStore):
    """鮮度は時間の経過だけで変わる。保存時に焼き込むと次の保存までずれ続ける。"""
    store.save(_entry(retrieved="2026-01-01"))

    assert store.index("tech", today=date(2026, 1, 10)).stale_count == 0
    assert store.index("tech", today=date(2026, 3, 1)).stale_count == 1


def test_search_finds_entries_the_index_body_does_not_mention(store: KnowledgeStore, tmp_path: Path):
    """索引は要約。索引で絞ると、要約に載らなかった語で実体を取りこぼす。"""
    store.save(_entry(note="リージョン別の制限がある"))
    (tmp_path / "tech" / "index.md").write_text(
        "---\ntype: index\nkind: tech\nentry_count: 1\ngenerated: '2026-07-01'\n---\n\n(空)\n",
        encoding="utf-8",
    )

    assert store.search("リージョン").total == 1


def test_search_truncates_by_char_budget_and_says_so(store: KnowledgeStore):
    for i in range(3):
        store.save(_entry(statement="あ" * 100 + str(i)))

    result = store.search(char_budget=150)

    assert (len(result.entries), result.total, result.truncated) == (1, 3, True)


def test_search_keeps_one_entry_even_when_it_exceeds_the_budget(store: KnowledgeStore):
    """1件も返さないと、呼び出し側は該当なしと区別できない。"""
    store.save(_entry(statement="あ" * 500))

    result = store.search(char_budget=10)

    assert (len(result.entries), result.truncated) == (1, False)


def test_project_index_reports_entry_count(md_backend: MarkdownKnowledgeBackend):
    md_backend.append(_project_entry())
    md_backend.append(_project_entry(statement="second"))

    index = md_backend.index("yoyaku")

    assert (index.entry_count, index.stale_count) == (2, None)


def test_sqlite_index_counts_without_an_index_file(sqlite_backend: SqliteKnowledgeBackend):
    sqlite_backend.append(_project_entry())

    assert sqlite_backend.index("yoyaku").entry_count == 1
