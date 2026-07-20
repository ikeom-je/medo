from pathlib import Path
from unittest.mock import MagicMock

from medo_etl.release_notes import ReleaseNote, fetch_release_notes, load_services


def test_load_services():
    services = load_services(Path(__file__).parent.parent / "services.yaml")
    slugs = [s.slug for s in services]
    assert "vertex-ai" in slugs and "cloud-run" in slugs
    va = next(s for s in services if s.slug == "vertex-ai")
    assert va.product_name == "Vertex AI"
    assert va.release_notes_url.startswith("https://")


def test_fetch_release_notes_builds_query_and_maps_rows():
    row = MagicMock()
    row.product_name = "Vertex AI"
    row.description = "Context caching is GA."
    row.release_note_type = "FEATURE"
    row.published_at = __import__("datetime").date(2026, 6, 20)
    bq = MagicMock()
    bq.query.return_value.result.return_value = [row]

    notes = fetch_release_notes(bq, ["Vertex AI"], since="2026-06-01")
    assert notes == [
        ReleaseNote(
            product_name="Vertex AI",
            description="Context caching is GA.",
            release_note_type="FEATURE",
            published_at="2026-06-20",
        )
    ]
    sql = bq.query.call_args.args[0]
    assert "bigquery-public-data.google_cloud_release_notes.release_notes" in sql
