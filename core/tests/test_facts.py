from datetime import date

import pytest
from medo_core.facts import Fact, FactStore, Verification
from medo_core.source_check import verify_fact
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
        verification=Verification(status="unverified", reason="test", checked="2026-07-01"),
    )
    base.update(kw)
    return Fact(**base)


def test_market_fact_requires_url_source():
    with pytest.raises(ValidationError):
        _fact(source="ヒアリングで聞いた")


def test_company_fact_accepts_hearing_source():
    f = _fact(kind="company", statement="現在の月間予約数は約1,200件", source="ヒアリング(2026-07-01 顧客X)",
              verification=Verification(status="not-applicable"))
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


@pytest.mark.parametrize("verification", [None, Verification(status="legacy")])
def test_save_rejects_missing_or_legacy_verification(tmp_path, verification):
    with pytest.raises(ValueError):
        FactStore(LocalJsonStorage(tmp_path)).save(
            "yoyaku", _fact().model_copy(update={"verification": verification})
        )


def test_old_json_is_labelled_on_read(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    storage.put("projects/yoyaku/facts/fact-1", _fact().model_dump(exclude={"verification"}))
    company = _fact(kind="company", source="ヒアリング", verification=None)
    storage.put("projects/yoyaku/facts/fact-2", company.model_dump(exclude={"verification"}))
    store = FactStore(storage)
    assert store.get("yoyaku", "fact-1").verification.status == "legacy"
    assert [fact.verification.status for fact in store.list("yoyaku")] == [
        "legacy", "not-applicable"
    ]


@pytest.mark.parametrize(
    ("kind", "status", "valid"),
    [
        ("market", "verified", True), ("market", "unverified", True),
        ("market", "not-applicable", False), ("market", "legacy", False),
        ("company", "not-applicable", True), ("company", "unverified", False),
        ("company", "verified", False),
    ],
)
def test_kind_limits_verification_state(kind, status, valid):
    data = dict(kind=kind, source="ヒアリング" if kind == "company" else "https://example.com",
                quote="3.2兆円", verification=Verification(status=status))
    if valid:
        _fact(**data)
    else:
        with pytest.raises(ValidationError):
            _fact(**data)


def test_verified_requires_quote_and_verify_fact_checks_body():
    with pytest.raises(ValidationError):
        _fact(verification=Verification(status="verified"))
    fact = _fact(quote="3.2兆円", value=3.2, unit="兆円")
    verified = verify_fact(fact, "市場は3.2兆円", checked="2026-09-28")
    assert verified.verification.status == "verified"
    assert verified.verification.checked == "2026-09-28"
    with pytest.raises(ValueError, match="quote-not-found"):
        verify_fact(fact, "市場は3.3兆円", checked="2026-09-28")
