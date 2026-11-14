from medo_core.storage import LocalJsonStorage
from medo_core.watermark import IdWatermark, IdWatermarkStore


def test_allocate_returns_sequential_ids_for_prefix():
    wm = IdWatermark()

    assert wm.allocate("as", 3) == ["as-1", "as-2", "as-3"]


def test_allocate_continues_from_previous_high_water_mark():
    wm = IdWatermark(marks={"as": 5})

    assert wm.allocate("as", 2) == ["as-6", "as-7"]


def test_allocate_does_not_reuse_id_of_deleted_node(tmp_path):
    store = IdWatermarkStore(LocalJsonStorage(tmp_path))
    wm = store.load("p1")
    wm.allocate("as", 3)
    store.save("p1", wm)

    reloaded = store.load("p1")

    assert reloaded.allocate("as", 1) == ["as-4"]


def test_prefixes_are_numbered_independently():
    wm = IdWatermark()
    wm.allocate("as", 2)

    assert wm.allocate("tb", 1) == ["tb-1"]


def test_load_returns_empty_watermark_for_unknown_project(tmp_path):
    store = IdWatermarkStore(LocalJsonStorage(tmp_path))

    assert store.load("unknown").marks == {}
