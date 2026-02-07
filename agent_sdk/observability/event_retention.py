"""Event retention policy helpers for run event storage."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Optional


@dataclass(frozen=True)
class EventRetentionPolicy:
    """Retention policy for persisted run events.

    Archiving is handled by run log exporters; retention only prunes storage.
    """

    max_events: Optional[int] = None
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "EventRetentionPolicy":
        raw = os.getenv("AGENT_SDK_EVENT_RETENTION_MAX_EVENTS")
        if not raw:
            return cls(max_events=None, enabled=False)
        try:
            max_events = int(raw)
        except ValueError as exc:
            raise ValueError("AGENT_SDK_EVENT_RETENTION_MAX_EVENTS must be an integer") from exc
        if max_events <= 0:
            return cls(max_events=None, enabled=False)
        return cls(max_events=max_events, enabled=True)

    def cutoff_seq(self, seq: Optional[int]) -> Optional[int]:
        if not self.enabled or self.max_events is None or seq is None:
            return None
        if seq < self.max_events:
            return None
        return seq - self.max_events + 1
