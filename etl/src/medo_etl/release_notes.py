"""リリースノートの決定論的取得(BigQuery公開データセット)。"""

from pathlib import Path

import yaml
from pydantic import BaseModel


class ReleaseNote(BaseModel):
    product_name: str
    description: str
    release_note_type: str
    published_at: str  # YYYY-MM-DD


class ServiceConfig(BaseModel):
    slug: str
    product_name: str
    release_notes_url: str


def load_services(path: Path) -> list[ServiceConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [ServiceConfig.model_validate(s) for s in data["services"]]


QUERY = """
SELECT product_name, description, release_note_type, published_at
FROM `bigquery-public-data.google_cloud_release_notes.release_notes`
WHERE product_name IN UNNEST(@products)
  AND published_at >= @since
ORDER BY published_at DESC
"""


def fetch_release_notes(bq_client, product_names: list[str], since: str) -> list[ReleaseNote]:
    from google.cloud import bigquery

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("products", "STRING", product_names),
            bigquery.ScalarQueryParameter("since", "DATE", since),
        ]
    )
    rows = bq_client.query(QUERY, job_config=job_config).result()
    return [
        ReleaseNote(
            product_name=row.product_name,
            description=row.description,
            release_note_type=row.release_note_type,
            published_at=row.published_at.isoformat(),
        )
        for row in rows
    ]
