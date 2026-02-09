"""PII redaction utilities for logs and events."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Any, Iterable, List, Pattern

from agent_sdk.observability.stream_envelope import StreamEnvelope
from dataclasses import replace


DEFAULT_PATTERNS = [
    # Email
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    # US phone numbers (basic)
    r"\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}",
    # US SSN
    r"\b\d{3}-\d{2}-\d{4}\b",
]


@dataclass(frozen=True)
class RedactionPolicy:
    enabled: bool = False
    patterns: List[str] = field(default_factory=lambda: DEFAULT_PATTERNS.copy())
    replacement: str = "[REDACTED]"

    @classmethod
    def from_env(cls) -> "RedactionPolicy":
        enabled = os.getenv("AGENT_SDK_PII_REDACTION_ENABLED", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        raw_patterns = os.getenv("AGENT_SDK_PII_REDACTION_PATTERNS", "")
        if raw_patterns.strip():
            patterns = [p.strip() for p in raw_patterns.split(",") if p.strip()]
            return cls(enabled=enabled, patterns=patterns)
        return cls(enabled=enabled)


class Redactor:
    def __init__(self, policy: RedactionPolicy):
        self._policy = policy
        self._patterns: List[Pattern[str]] = []
        if self._policy.enabled:
            self._patterns = [re.compile(p) for p in self._policy.patterns]

    @property
    def enabled(self) -> bool:
        return self._policy.enabled

    def redact_text(self, value: str) -> str:
        if not self.enabled or not value:
            return value
        redacted = value
        for pattern in self._patterns:
            redacted = pattern.sub(self._policy.replacement, redacted)
        return redacted

    def redact_value(self, value: Any) -> Any:
        if not self.enabled:
            return value
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, list):
            return [self.redact_value(item) for item in value]
        if isinstance(value, dict):
            return {key: self.redact_value(val) for key, val in value.items()}
        return value

    def redact_event(self, event: StreamEnvelope) -> StreamEnvelope:
        if not self.enabled:
            return event
        payload = self.redact_value(event.payload)
        metadata = self.redact_value(event.metadata)
        return replace(event, payload=payload, metadata=metadata)

    def redact_metadata(self, metadata: dict) -> dict:
        return self.redact_value(metadata)
