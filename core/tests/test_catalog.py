from datetime import date
from pathlib import Path

import pytest
from medo_core.catalog import CatalogEntry, CatalogStore
from medo_core.storage import LocalJsonStorage
from pydantic import ValidationError


def _entry(**kw) -> CatalogEntry:
    base = dict(
        service="vertex-ai",
        feature="context-caching",
        launch_stage="GA",
        since="2025-11-01",
        summary="プロンプトの共通部分をキャッシュして入力コストを削減する",
        sources=["https://cloud.google.com/vertex-ai/docs/release-notes"],
        last_verified="2026-07-01",
    )
    base.update(kw)
    return CatalogEntry(**base)


@pytest.fixture
def store(tmp_path: Path) -> CatalogStore:
    return CatalogStore(LocalJsonStorage(tmp_path))


def test_entry_id():
    assert _entry().entry_id == "vertex-ai__context-caching"


def test_sources_required():
    with pytest.raises(ValidationError):
        _entry(sources=[])


def test_stale_when_older_than_30_days():
    e = _entry(last_verified="2026-05-01")
    assert e.is_stale(today=date(2026, 7, 5)) is True
    assert _entry(last_verified="2026-06-20").is_stale(today=date(2026, 7, 5)) is False


def test_upsert_and_get(store: CatalogStore):
    store.upsert(_entry())
    got = store.get("vertex-ai", "context-caching")
    assert got is not None and got.launch_stage == "GA"
    assert store.get("vertex-ai", "nashi") is None


def test_search_matches_feature_summary_caveats(store: CatalogStore):
    store.upsert(_entry())
    store.upsert(
        _entry(
            feature="batch-prediction",
            summary="バッチ推論",
            caveats=["リージョン制限あり"],
        )
    )
    store.upsert(_entry(service="cloud-run", feature="gpu", summary="GPUサポート"))

    assert [e.feature for e in store.search("caching")] == ["context-caching"]
    assert [e.feature for e in store.search("リージョン")] == ["batch-prediction"]
    assert {e.service for e in store.search("", service="vertex-ai")} == {"vertex-ai"}
    assert len(store.search("")) == 3
    assert len(store.search("", limit=2)) == 2
