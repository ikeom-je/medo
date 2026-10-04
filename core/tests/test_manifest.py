from medo_core.manifest import (
    ChangeManifest,
    ManifestStore,
    SectionChange,
    changed_sections,
    fold_substantive_sections,
    is_text_only_change,
)
from medo_core.storage import LocalJsonStorage


def _doc(**kw) -> dict:
    base = {
        "goal": "",
        "background": "",
        "as_is": [],
        "to_be": [],
        "gaps": [],
        "constraints": [],
        "stakeholders": [],
        "attempts": [],
        "challenges": [],
        "kpis": [],
        "bottlenecks": [],
        "hypotheses": [],
        "open_questions": [],
        "principles": [],
        "functional": [],
        "non_functional": {},
        "sources": [],
        "industry": "",
    }
    base.update(kw)
    return base


def test_first_version_reports_only_filled_sections():
    """初版で空のセクションまで変更扱いにすると、round_countが1周目から
    進んでしまう。"""
    new = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])

    assert changed_sections({}, new) == ["as_is"]


def test_changed_sections_detects_added_node():
    old = _doc()
    new = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])

    assert changed_sections(old, new) == ["as_is"]


def test_changed_sections_detects_text_edit_of_core_node():
    """往復とは本文を精緻化する工程そのもの。軽微と分類すると意味が変わった
    生成物が最新扱いのまま残る。"""
    old = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])
    new = _doc(as_is=[{"id": "as-1", "text": "紙の伝票を手入力", "visibility": "internal"}])

    assert changed_sections(old, new) == ["as_is"]


def test_changed_sections_returns_empty_when_identical():
    doc = _doc(goal="半日で目処を立てる")

    assert changed_sections(doc, doc) == []


def test_changed_sections_reports_each_changed_section():
    old = _doc()
    new = _doc(
        as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}],
        constraints=[{"id": "cs-1", "text": "予算300万円"}],
    )

    assert changed_sections(old, new) == ["as_is", "constraints"]


def test_fold_marks_section_substantive_when_any_version_changed_it():
    manifests = [
        ChangeManifest(version=2, changes=[SectionChange(section="as_is")],
                       recorded_on="2026-08-01"),
        ChangeManifest(version=3, changes=[SectionChange(section="to_be")],
                       recorded_on="2026-08-02"),
    ]

    assert fold_substantive_sections(manifests, from_version=1) == {"as_is", "to_be"}


def test_fold_ignores_versions_at_or_before_from_version():
    manifests = [
        ChangeManifest(version=2, changes=[SectionChange(section="as_is")],
                       recorded_on="2026-08-01"),
        ChangeManifest(version=3, changes=[SectionChange(section="to_be")],
                       recorded_on="2026-08-02"),
    ]

    assert fold_substantive_sections(manifests, from_version=2) == {"to_be"}


def test_text_only_edit_can_be_declared_editorial():
    old = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])
    new = _doc(as_is=[{"id": "as-1", "text": "紙の伝票を手入力", "visibility": "internal"}])

    assert is_text_only_change("as_is", old, new) is True


def test_added_node_cannot_be_declared_editorial():
    """宣言を無条件に信じると、追加・削除まで陳腐化判定から隠せてしまう。"""
    old = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"}])
    new = _doc(as_is=[{"id": "as-1", "text": "手作業", "visibility": "internal"},
                      {"id": "as-2", "text": "追加", "visibility": "internal"}])

    assert is_text_only_change("as_is", old, new) is False


def test_confidence_change_cannot_be_declared_editorial():
    old = _doc(to_be=[{"id": "tb-1", "text": "自動化", "confidence": "assumed"}])
    new = _doc(to_be=[{"id": "tb-1", "text": "自動化", "confidence": "confirmed"}])

    assert is_text_only_change("to_be", old, new) is False


def test_non_node_section_cannot_be_declared_editorial():
    """sources は list[str] であってノード構造を持たない。textだけの差分を切り出せない。"""
    assert is_text_only_change("sources", {"sources": ["https://a/1"]},
                               {"sources": ["https://a/2"]}) is False


def test_scalar_text_section_can_be_declared_editorial():
    assert is_text_only_change("goal", {"goal": "半日で目処"}, {"goal": "半日で目処が立つ"}) is True


def test_dict_section_cannot_be_declared_editorial():
    """non_functional は値の変更が実質変更(陳腐化の粒度表)。"""
    assert is_text_only_change("non_functional", {"non_functional": {"a": "1"}},
                               {"non_functional": {"a": "2"}}) is False


def test_fold_excludes_editorial_declarations():
    manifests = [
        ChangeManifest(
            version=2,
            changes=[SectionChange(section="as_is", change_kind="editorial")],
            recorded_on="2026-08-01",
        )
    ]

    assert fold_substantive_sections(manifests, from_version=1) == set()


def test_fold_excludes_id_only_migration_version():
    """初回ID採番は意味上の変更ではないため陳腐化を引き起こさない。"""
    manifests = [
        ChangeManifest(
            version=2,
            changes=[SectionChange(section="challenges")],
            id_only_migration=True,
            recorded_on="2026-08-01",
        )
    ]

    assert fold_substantive_sections(manifests, from_version=1) == set()


def test_store_round_trips_manifests_in_version_order(tmp_path):
    store = ManifestStore(LocalJsonStorage(tmp_path))
    store.save("p1", ChangeManifest(version=1, recorded_on="2026-08-01"))
    store.save("p1", ChangeManifest(version=2, changes=[SectionChange(section="to_be")],
                                    recorded_on="2026-08-02"))

    assert [m.version for m in store.list("p1")] == [1, 2]
