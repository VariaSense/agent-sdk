"""Provider clients and error normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ProviderError(Exception):
    status_code: int
    code: str
    message: str
    retriable: bool = False

    def __str__(self) -> str:
        return f"{self.code} ({self.status_code}): {self.message}"


def normalize_http_error(status_code: int, body: Dict[str, Any]) -> ProviderError:
    code = body.get("error", {}).get("code") or body.get("code") or "provider_error"
    message = body.get("error", {}).get("message") or body.get("message") or "Provider error"
    retriable = status_code in {408, 409, 429, 500, 502, 503, 504}
    return ProviderError(status_code=status_code, code=code, message=message, retriable=retriable)
