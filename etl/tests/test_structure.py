import json

from medo_etl.release_notes import ReleaseNote, ServiceConfig
from medo_etl.structure import structure_notes

SERVICE = ServiceConfig(
    slug="vertex-ai",
    product_name="Vertex AI",
    release_notes_url="https://cloud.google.com/vertex-ai/docs/release-notes",
)

NOTES = [
    ReleaseNote(
        product_name="Vertex AI",
        description="Context caching is now GA.",
        release_note_type="FEATURE",
        published_at="2026-06-20",
    )
]


def _fake_generate(valid: list[dict]):
    def generate(prompt: str) -> str:
        assert "Context caching" in prompt  # ノート本文がプロンプトに含まれる
        return json.dumps(valid)

    return generate


def test_non_array_output_reported_as_error():
    entries, errors = structure_notes(
        SERVICE, NOTES, lambda p: '{"not": "array"}', today="2026-07-20"
    )
    assert entries == [] and len(errors) == 1


def test_non_dict_items_reported_without_crash():
    entries, errors = structure_notes(SERVICE, NOTES, lambda p: '["just-a-string"]', today="2026-07-20")
    assert entries == [] and len(errors) == 1


def test_structure_notes_returns_validated_entries():
    generate = _fake_generate(
        [
            {
                "feature": "context-caching",
                "launch_stage": "GA",
                "since": "2026-06-20",
                "summary": "コンテキストキャッシュがGA",
                "caveats": [],
            }
        ]
    )
    entries, errors = structure_notes(SERVICE, NOTES, generate, today="2026-07-05")
    assert errors == []
    assert len(entries) == 1
    e = entries[0]
    assert e.service == "vertex-ai"
    assert e.launch_stage == "GA"
    assert e.last_verified == "2026-07-05"
    assert e.sources == ["https://cloud.google.com/vertex-ai/docs/release-notes"]


def test_structure_notes_rejects_invalid_items_but_keeps_valid():
    generate = _fake_generate(
        [
            {"feature": "ok-feature", "launch_stage": "Preview", "summary": "ok", "caveats": []},
            {"feature": "bad-feature", "launch_stage": "不正な値", "summary": "ng", "caveats": []},
        ]
    )
    entries, errors = structure_notes(SERVICE, NOTES, generate, today="2026-07-05")
    assert [e.feature for e in entries] == ["ok-feature"]
    assert len(errors) == 1 and "bad-feature" in errors[0]


def test_structure_notes_rejects_broken_json():
    entries, errors = structure_notes(SERVICE, NOTES, lambda p: "not json", today="2026-07-05")
    assert entries == [] and len(errors) == 1
