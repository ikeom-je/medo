from datetime import date
from pathlib import Path

import pytest
from medo_core.nodes import AsIs, Challenge, Gap, OpenQuestion, ToBe
from medo_core.requirements import FunctionalRequirement, RequirementsDoc, RequirementsStore
from medo_core.storage import LocalJsonStorage

TODAY = date(2026, 8, 30)


@pytest.fixture
def store(tmp_path: Path) -> RequirementsStore:
    return RequirementsStore(LocalJsonStorage(tmp_path))


def _store(tmp_path) -> RequirementsStore:
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
    from medo_core.nodes import Challenge
    from medo_core.requirements import ConfidenceItem

    doc = _doc(
        background="インバウンド客の増加と人手不足が同時進行",
        principles=[ConfidenceItem(text="地域の食文化を海外客に開く", confidence="confirmed")],
        challenges=[Challenge(text="外国語の電話予約に対応できず機会損失")],
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


def test_knowledge_backend_defaults_to_markdown():
    doc = RequirementsDoc(project="yoyaku")
    assert doc.knowledge_backend == "markdown"


def test_knowledge_backend_accepts_sqlite():
    doc = RequirementsDoc(project="yoyaku", knowledge_backend="sqlite")
    assert doc.knowledge_backend == "sqlite"


def test_open_questions_accepts_legacy_string_list():
    """フェーズ1のデータは list[str]。読み込み時にID付きへ変換する。"""
    doc = RequirementsDoc.model_validate(
        {"project": "p1", "open_questions": ["予算は未確定"]}
    )

    assert doc.open_questions[0].text == "予算は未確定"
    assert doc.open_questions[0].id == ""


def test_open_questions_accepts_new_object_form():
    doc = RequirementsDoc.model_validate(
        {"project": "p1", "open_questions": [{"id": "oq-1", "text": "予算は未確定"}]}
    )

    assert doc.open_questions[0].id == "oq-1"


def test_challenges_reads_legacy_confidence_item_without_id():
    """Challenge は ConfidenceItem の上位互換。既存JSONはidが無い状態で読める。"""
    doc = RequirementsDoc.model_validate(
        {
            "project": "p1",
            "challenges": [{"text": "後戻りが起きる", "confidence": "confirmed"}],
        }
    )

    assert doc.challenges[0].id == ""
    assert doc.challenges[0].confidence == "confirmed"
    assert doc.challenges[0].scope == "core"


def test_new_sections_default_to_empty():
    doc = RequirementsDoc(project="p1")

    assert doc.as_is == []
    assert doc.to_be == []
    assert doc.attempts == []


def test_holds_as_is_nodes():
    doc = RequirementsDoc(
        project="p1",
        as_is=[AsIs(id="as-1", text="紙の伝票を手入力", visibility="internal")],
    )

    assert doc.as_is[0].visibility == "internal"


def test_diff_compares_open_questions_by_text(tmp_path_factory):
    """pydanticモデルはhashableでないため、既存のset比較では落ちる。"""
    store = RequirementsStore(LocalJsonStorage(tmp_path_factory.mktemp("d")))
    store.save(
        "p1",
        RequirementsDoc(
            project="p1", open_questions=[OpenQuestion(text="予算は未確定")]
        ),
    )
    doc = store.get("p1")
    doc.open_questions.append(OpenQuestion(text="体制は未確定"))
    store.save("p1", doc)

    assert store.diff("p1")["open_questions_added"] == ["体制は未確定"]


def test_challenge_and_open_question_are_node_types():
    doc = RequirementsDoc(
        project="p1",
        challenges=[Challenge(text="後戻り")],
        open_questions=[OpenQuestion(text="予算")],
    )

    assert isinstance(doc.challenges[0], Challenge)
    assert isinstance(doc.open_questions[0], OpenQuestion)


def test_save_assigns_ids_to_empty_id_nodes(tmp_path):
    store = _store(tmp_path)
    doc = RequirementsDoc(
        project="p1",
        as_is=[
            AsIs(text="手作業", visibility="internal"),
            AsIs(text="公表", visibility="public"),
        ],
    )

    store.save("p1", doc, today=TODAY)

    saved = store.get("p1")
    assert [n.id for n in saved.as_is] == ["as-1", "as-2"]


def test_save_does_not_reuse_id_of_deleted_node(tmp_path):
    store = _store(tmp_path)
    store.save(
        "p1",
        RequirementsDoc(
            project="p1",
            as_is=[
                AsIs(text="a", visibility="internal"),
                AsIs(text="b", visibility="internal"),
            ],
        ),
        today=TODAY,
    )
    kept = store.get("p1").as_is[0]

    store.save("p1", RequirementsDoc(project="p1", as_is=[kept]), today=TODAY)
    store.save(
        "p1",
        RequirementsDoc(
            project="p1",
            as_is=[kept, AsIs(text="c", visibility="internal")],
        ),
        today=TODAY,
    )

    assert [n.id for n in store.get("p1").as_is] == ["as-1", "as-3"]


def test_save_rejects_duplicate_ids_within_document(tmp_path):
    store = _store(tmp_path)
    doc = RequirementsDoc(
        project="p1",
        as_is=[
            AsIs(id="as-1", text="a", visibility="internal"),
            AsIs(id="as-1", text="b", visibility="internal"),
        ],
    )

    with pytest.raises(ValueError, match="重複"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_id_absent_from_previous_version(tmp_path):
    """ホストLLMが書き写す際の勝手なリナンバリングを機械的に検出する。"""
    store = _store(tmp_path)
    store.save(
        "p1",
        RequirementsDoc(
            project="p1", as_is=[AsIs(text="a", visibility="internal")]
        ),
        today=TODAY,
    )

    doc = RequirementsDoc(
        project="p1", as_is=[AsIs(id="as-9", text="a", visibility="internal")]
    )

    with pytest.raises(ValueError, match="as-9"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_link_to_unknown_node(tmp_path):
    store = _store(tmp_path)
    doc = RequirementsDoc(
        project="p1", gaps=[Gap(text="乖離", kind="goal", from_as_is=["as-99"])]
    )

    with pytest.raises(ValueError, match="as-99"):
        store.save("p1", doc, today=TODAY)


def test_save_records_manifest_of_changed_sections(tmp_path):
    from medo_core.manifest import ManifestStore

    storage = LocalJsonStorage(tmp_path)
    store = RequirementsStore(storage)
    store.save("p1", RequirementsDoc(project="p1"), today=TODAY)
    store.save(
        "p1",
        RequirementsDoc(project="p1", to_be=[ToBe(text="自動化されている")]),
        today=TODAY,
    )

    manifests = ManifestStore(storage).list("p1")
    assert [c.section for c in manifests[1].changes] == ["to_be"]


def test_save_marks_declared_sections_as_editorial(tmp_path):
    from medo_core.manifest import ManifestStore

    storage = LocalJsonStorage(tmp_path)
    store = RequirementsStore(storage)
    store.save(
        "p1",
        RequirementsDoc(project="p1", to_be=[ToBe(id="", text="自動化")]),
        today=TODAY,
    )
    kept = store.get("p1").to_be[0]
    store.save(
        "p1",
        RequirementsDoc(
            project="p1",
            to_be=[kept.model_copy(update={"text": "自動化されている"})],
        ),
        editorial_sections=("to_be",),
        today=TODAY,
    )

    manifests = ManifestStore(storage).list("p1")
    assert manifests[1].changes[0].change_kind == "editorial"


def test_save_flags_first_id_assignment_as_id_only_migration(tmp_path):
    """初回ID採番だけの保存は陳腐化を引き起こさない。"""
    from medo_core.manifest import ManifestStore

    storage = LocalJsonStorage(tmp_path)
    storage.put(
        "projects/p1/requirements/v1",
        {
            "project": "p1",
            "version": 1,
            "challenges": [{"text": "後戻りが起きる", "confidence": "confirmed"}],
        },
    )
    store = RequirementsStore(storage)
    doc = store.get("p1")

    store.save("p1", doc, today=TODAY)

    manifests = ManifestStore(storage).list("p1")
    assert manifests[-1].id_only_migration is True


def test_save_rejects_bottleneck_that_is_not_confirmed(tmp_path):
    """bottlenecks は検証・合意済みの真因のみを持つ。"""
    from medo_core.nodes import Bottleneck

    store = _store(tmp_path)
    doc = RequirementsDoc(project="p1", bottlenecks=[Bottleneck(text="承認3階層")])

    with pytest.raises(ValueError, match="confirmed"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_perception_gap_without_both_visibilities(tmp_path):
    store = _store(tmp_path)
    store.save(
        "p1",
        RequirementsDoc(
            project="p1", as_is=[AsIs(text="公表", visibility="public")]
        ),
        today=TODAY,
    )
    public_id = store.get("p1").as_is[0].id

    doc = RequirementsDoc(
        project="p1",
        as_is=[store.get("p1").as_is[0]],
        gaps=[Gap(text="乖離", kind="perception", from_as_is=[public_id])],
    )

    with pytest.raises(ValueError, match="perception"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_bottleneck_promoted_from_unvalidated_hypothesis(tmp_path):
    from medo_core.nodes import Bottleneck, Hypothesis

    store = _store(tmp_path)
    store.save(
        "p1",
        RequirementsDoc(
            project="p1",
            hypotheses=[Hypothesis(kind="cause", statement="承認階層が原因")],
        ),
        today=TODAY,
    )
    hyp = store.get("p1").hypotheses[0]

    doc = RequirementsDoc(
        project="p1",
        hypotheses=[hyp],
        bottlenecks=[
            Bottleneck(
                text="承認3階層",
                confidence="confirmed",
                from_hypothesis=hyp.id,
            )
        ],
    )

    with pytest.raises(ValueError, match="validated"):
        store.save("p1", doc, today=TODAY)


def test_save_rejects_evidenced_by_pointing_to_unknown_node(tmp_path):
    store = _store(tmp_path)
    doc = RequirementsDoc(
        project="p1", to_be=[ToBe(text="自動化", evidenced_by=["as-99"])]
    )

    with pytest.raises(ValueError, match="as-99"):
        store.save("p1", doc, today=TODAY)


def test_save_accepts_evidenced_by_pointing_to_event(tmp_path):
    """誰の発言が理想像を形にしたかをイベントまで遡れるようにする。"""
    store = _store(tmp_path)

    store.save(
        "p1",
        RequirementsDoc(
            project="p1", to_be=[ToBe(text="自動化", evidenced_by=["ev-3"])]
        ),
        today=TODAY,
    )

    assert store.get("p1").to_be[0].evidenced_by == ["ev-3"]


def test_save_rejects_promotion_source_pointing_to_goal_gap(tmp_path):
    from medo_core.nodes import PromotionSource

    store = _store(tmp_path)
    store.save(
        "p1",
        RequirementsDoc(project="p1", gaps=[Gap(text="乖離", kind="goal")]),
        today=TODAY,
    )
    gap_id = store.get("p1").gaps[0].id

    doc = RequirementsDoc(
        project="p1",
        gaps=[store.get("p1").gaps[0]],
        challenges=[
            Challenge(
                text="どちらを前提にするか",
                promoted_from=PromotionSource(kind="internal_conflict", ref=gap_id),
            )
        ],
    )

    with pytest.raises(ValueError, match="internal_conflict"):
        store.save("p1", doc, today=TODAY)
