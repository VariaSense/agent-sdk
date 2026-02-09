"""Idempotency key store for run creation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class IdempotencyRecord:
    key: str
    payload: dict
    created_at: datetime


class IdempotencyStore:
    def __init__(self, ttl_minutes: int = 60) -> None:
        self._records: Dict[str, IdempotencyRecord] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    def get(self, key: str) -> Optional[dict]:
        record = self._records.get(key)
        if not record:
            return None
        if _now() - record.created_at > self._ttl:
            self._records.pop(key, None)
            return None
        return record.payload

    def set(self, key: str, payload: dict) -> None:
        self._records[key] = IdempotencyRecord(key=key, payload=payload, created_at=_now())
