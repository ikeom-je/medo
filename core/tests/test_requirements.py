from pathlib import Path

import pytest
from medo_core.requirements import FunctionalRequirement, RequirementsDoc, RequirementsStore
from medo_core.storage import LocalJsonStorage


@pytest.fixture
def store(tmp_path: Path) -> RequirementsStore:
    return RequirementsStore(LocalJsonStorage(tmp_path))


def _doc(**kw) -> RequirementsDoc:
    base = dict(
        project="yoyaku",
        goal="飲食店の予約システム",
        industry="飲食",
        functional=[FunctionalRequirement(text="ネット予約", confidence="confirmed")],
        open_questions=["ピーク時同時予約数は?"],
    )
    base.update(kw)
    return RequirementsDoc(**base)


def test_save_assigns_incrementing_versions(store: RequirementsStore):
    assert store.save("yoyaku", _doc()) == 1
    assert store.save("yoyaku", _doc()) == 2
    assert store.latest_version("yoyaku") == 2


def test_get_latest_and_specific_version(store: RequirementsStore):
    store.save("yoyaku", _doc(goal="v1のゴール"))
    store.save("yoyaku", _doc(goal="v2のゴール"))
    assert store.get("yoyaku").goal == "v2のゴール"
    assert store.get("yoyaku", version=1).goal == "v1のゴール"
    assert store.get("nashi") is None


def test_confidence_defaults_to_open():
    fr = FunctionalRequirement(text="通知機能")
    assert fr.confidence == "open"


def test_business_context_fields_roundtrip(store: RequirementsStore):
    from medo_core.requirements import ConfidenceItem

    doc = _doc(
        background="インバウンド客の増加と人手不足が同時進行",
        principles=[ConfidenceItem(text="地域の食文化を海外客に開く", confidence="confirmed")],
        challenges=[ConfidenceItem(text="外国語の電話予約に対応できず機会損失")],
    )
    store.save("yoyaku", doc)
    got = store.get("yoyaku")
    assert got.background == "インバウンド客の増加と人手不足が同時進行"
    assert got.principles[0].confidence == "confirmed"
    assert got.challenges[0].confidence == "open"  # 既定はopen


def test_backward_compat_docs_without_new_fields(store: RequirementsStore):
    raw = _doc().model_dump(mode="json")
    for key in ("background", "principles", "challenges"):
        raw.pop(key, None)
    doc = RequirementsDoc.model_validate(raw)
    assert doc.background == "" and doc.principles == [] and doc.challenges == []


def test_diff_between_latest_two_versions(store: RequirementsStore):
    store.save(
        "yoyaku",
        _doc(
            functional=[FunctionalRequirement(text="ネット予約")],
            open_questions=["ピーク時同時予約数は?", "多言語対応は?"],
        ),
    )
    store.save(
        "yoyaku",
        _doc(
            functional=[
                FunctionalRequirement(text="ネット予約"),
                FunctionalRequirement(text="LINE通知"),
            ],
            open_questions=["多言語対応は?"],
        ),
    )
    d = store.diff("yoyaku")
    assert d["from"] == 1 and d["to"] == 2
    assert d["functional_added"] == ["LINE通知"]
    assert d["functional_removed"] == []
    assert d["open_questions_resolved"] == ["ピーク時同時予約数は?"]
    assert d["open_questions_added"] == []


def test_diff_with_single_version(store: RequirementsStore):
    store.save("yoyaku", _doc())
    d = store.diff("yoyaku")
    assert d["from"] == 0 and d["to"] == 1
    assert d["functional_added"] == []
