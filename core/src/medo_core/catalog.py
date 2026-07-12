"""鮮度メタデータ付きカタログ。出典必須・金額は焼き込まない(SKU参照のみ)。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from medo_core.storage import Storage

STALE_THRESHOLD_DAYS = 30

LaunchStage = Literal["GA", "Preview", "Deprecated"]


class CatalogEntry(BaseModel):
    service: str
    feature: str
    launch_stage: LaunchStage
    since: str | None = None
    summary: str
    pricing_refs: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    sources: list[str] = Field(min_length=1)
    last_verified: str

    @property
    def entry_id(self) -> str:
        return f"{self.service}__{self.feature}"

    def is_stale(self, today: date | None = None, threshold_days: int = STALE_THRESHOLD_DAYS) -> bool:
        today = today or date.today()
        verified = date.fromisoformat(self.last_verified)
        return (today - verified).days > threshold_days


class CatalogStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def upsert(self, entry: CatalogEntry) -> None:
        self._storage.put(f"catalog/{entry.entry_id}", entry.model_dump(mode="json"))

    def get(self, service: str, feature: str) -> CatalogEntry | None:
        raw = self._storage.get(f"catalog/{service}__{feature}")
        return CatalogEntry.model_validate(raw) if raw else None

    def search(self, query: str = "", service: str | None = None, limit: int = 10) -> list[CatalogEntry]:
        q = query.lower()
        results: list[CatalogEntry] = []
        for path in self._storage.list("catalog"):
            raw = self._storage.get(path)
            entry = CatalogEntry.model_validate(raw)
            if service and entry.service != service:
                continue
            haystack = " ".join([entry.feature, entry.summary, *entry.caveats]).lower()
            if q and q not in haystack:
                continue
            results.append(entry)
            if len(results) >= limit:
                break
        return results
