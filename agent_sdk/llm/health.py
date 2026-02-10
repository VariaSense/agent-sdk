from __future__ import annotations

from dataclasses import dataclass
from typing import List
import os


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    healthy: bool
    reason: str = ""


class ProviderHealthMonitor:
    def __init__(self) -> None:
        self._overrides = {
            "openai": os.getenv("AGENT_SDK_PROVIDER_HEALTH_OPENAI"),
            "anthropic": os.getenv("AGENT_SDK_PROVIDER_HEALTH_ANTHROPIC"),
            "azure": os.getenv("AGENT_SDK_PROVIDER_HEALTH_AZURE"),
        }

    def _override(self, provider: str) -> bool | None:
        override = self._overrides.get(provider)
        if not override:
            return None
        return override.lower() in {"1", "true", "yes", "on"}

    def check(self, provider: str) -> ProviderHealth:
        override = self._override(provider)
        if override is not None:
            return ProviderHealth(provider=provider, healthy=override, reason="override")
        if provider == "openai":
            if os.getenv("OPENAI_API_KEY"):
                return ProviderHealth(provider=provider, healthy=True)
            return ProviderHealth(provider=provider, healthy=False, reason="OPENAI_API_KEY missing")
        if provider == "anthropic":
            if os.getenv("ANTHROPIC_API_KEY"):
                return ProviderHealth(provider=provider, healthy=True)
            return ProviderHealth(provider=provider, healthy=False, reason="ANTHROPIC_API_KEY missing")
        if provider == "azure":
            if os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT"):
                return ProviderHealth(provider=provider, healthy=True)
            return ProviderHealth(provider=provider, healthy=False, reason="AZURE_OPENAI_* missing")
        return ProviderHealth(provider=provider, healthy=True)

    def check_all(self, providers: List[str]) -> List[ProviderHealth]:
        return [self.check(provider) for provider in providers]
