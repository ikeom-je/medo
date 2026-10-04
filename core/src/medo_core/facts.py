"""市場・国策・業界動向・個社ファクト。出典必須(仮定はファクトにしない=fermi側のassumeのみ)。"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, model_validator

from medo_core.storage import Storage

FACT_STALE_THRESHOLD_DAYS = 180

FactKind = Literal["market", "policy", "trend", "company"]
_URL_KINDS = {"market", "policy", "trend"}


class Verification(BaseModel):
    status: Literal["verified", "unverified", "not-applicable", "legacy"]
    reason: str = ""
    checked: str = ""
    support: Literal["supported", "doubtful", "unjudged"] = "unjudged"


class Fact(BaseModel):
    fact_id: str = ""
    kind: FactKind
    statement: str
    value: float | None = None
    unit: str = ""
    source: str
    retrieved: str  # ISO日付 YYYY-MM-DD
    note: str = ""
    quote: str = ""
    verification: Verification | None = None

    @model_validator(mode="after")
    def _validate(self) -> "Fact":
        if not self.source.strip():
            raise ValueError("source は必須です(出典のないファクトは保存できません)")
        if self.kind in _URL_KINDS:
            parsed = urlparse(self.source)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"kind={self.kind} の source はURLである必要があります")
        try:
            date.fromisoformat(self.retrieved)
        except ValueError as e:
            raise ValueError(f"retrieved はISO日付(YYYY-MM-DD)である必要があります: {e}") from e
        if self.verification is not None:
            status = self.verification.status
            if self.kind == "company" and status != "not-applicable":
                raise ValueError("company の verification は not-applicable のみです")
            if self.kind in _URL_KINDS and status not in ("verified", "unverified"):
                raise ValueError(f"kind={self.kind} の verification は verified/unverified のみです")
            if status == "verified" and not self.quote.strip():
                raise ValueError("verified には quote が必要です")
        return self

    def is_stale(
        self, today: date | None = None, threshold_days: int = FACT_STALE_THRESHOLD_DAYS
    ) -> bool:
        today = today or date.today()
        return (today - date.fromisoformat(self.retrieved)).days > threshold_days


class FactStore:
    def __init__(self, storage: Storage):
        self._storage = storage

    def _prefix(self, project_id: str) -> str:
        return f"projects/{project_id}/facts"

    def save(self, project_id: str, fact: Fact) -> str:
        if fact.verification is None or fact.verification.status == "legacy":
            raise ValueError("保存には legacy 以外の verification が必要です")
        fact = Fact.model_validate(fact.model_dump())
        if not fact.fact_id:
            nums = []
            for path in self._storage.list(self._prefix(project_id)):
                m = re.fullmatch(r"fact-(\d+)", path.rsplit("/", 1)[1])
                if m:
                    nums.append(int(m.group(1)))
            fact = fact.model_copy(update={"fact_id": f"fact-{max(nums, default=0) + 1}"})
        self._storage.put(f"{self._prefix(project_id)}/{fact.fact_id}", fact.model_dump(mode="json"))
        return fact.fact_id

    def get(self, project_id: str, fact_id: str) -> Fact | None:
        raw = self._storage.get(f"{self._prefix(project_id)}/{fact_id}")
        return self._from_storage(raw) if raw else None

    def list(self, project_id: str) -> list[Fact]:
        return [
            self._from_storage(self._storage.get(p))
            for p in self._storage.list(self._prefix(project_id))
        ]

    @staticmethod
    def _from_storage(raw: dict) -> Fact:
        fact = Fact.model_validate(raw)
        if fact.verification is None:
            status = "not-applicable" if fact.kind == "company" else "legacy"
            fact = fact.model_copy(update={"verification": Verification(status=status)})
        return fact
