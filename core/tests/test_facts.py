from datetime import date

import pytest
from medo_core.facts import Fact, FactStore
from medo_core.storage import LocalJsonStorage
from pydantic import ValidationError


def _fact(**kw) -> Fact:
    base = dict(
        kind="market",
        statement="訪日外国人旅行者数 3,687万人(2024年)",
        value=36870000.0,
        unit="人",
        source="https://www.jnto.go.jp/statistics/",
        retrieved="2026-07-01",
    )
    base.update(kw)
    return Fact(**base)


def test_market_fact_requires_url_source():
    with pytest.raises(ValidationError):
        _fact(source="ヒアリングで聞いた")


def test_company_fact_accepts_hearing_source():
    f = _fact(kind="company", statement="現在の月間予約数は約1,200件", source="ヒアリング(2026-07-01 顧客X)")
    assert f.kind == "company"


def test_empty_source_rejected():
    with pytest.raises(ValidationError):
        _fact(kind="company", source="   ")


def test_invalid_retrieved_date_rejected():
    with pytest.raises(ValidationError):
        _fact(retrieved="not-a-date")


def test_stale_when_older_than_180_days():
    assert _fact(retrieved="2026-01-01").is_stale(today=date(2026, 7, 12)) is True
    assert _fact(retrieved="2026-02-01").is_stale(today=date(2026, 7, 12)) is False


def test_save_assigns_incrementing_fact_ids(tmp_path):
    store = FactStore(LocalJsonStorage(tmp_path))
    assert store.save("yoyaku", _fact()) == "fact-1"
    assert store.save("yoyaku", _fact(statement="外食単価")) == "fact-2"
    got = store.get("yoyaku", "fact-1")
    assert got is not None and got.value == 36870000.0
    assert len(store.list("yoyaku")) == 2
    assert store.list("nashi") == []
