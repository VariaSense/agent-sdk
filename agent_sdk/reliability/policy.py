from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
import time

from agent_sdk.core.retry import retry_with_backoff, sync_retry_with_backoff


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 2
    base_delay: float = 0.5
    max_delay: float = 5.0
    exponential_base: float = 2.0


@dataclass(frozen=True)
class CircuitBreakerPolicy:
    failure_threshold: int = 3
    reset_timeout_seconds: float = 30.0


@dataclass(frozen=True)
class FallbackPolicy:
    fallback_models: list[str] = field(default_factory=list)


class CircuitBreaker:
    def __init__(self, policy: CircuitBreakerPolicy) -> None:
        self._policy = policy
        self._failures = 0
        self._opened_at: Optional[float] = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        elapsed = time.time() - self._opened_at
        if elapsed >= self._policy.reset_timeout_seconds:
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._policy.failure_threshold:
            self._opened_at = time.time()


class ReplayStore:
    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        self._data = data or {}

    def get(self, key: str) -> Optional[Any]:
        return self._data.get(key)

    def record(self, key: str, value: Any) -> None:
        self._data[key] = value


class ReliabilityManager:
    def __init__(
        self,
        retry_policy: Optional[RetryPolicy] = None,
        breaker_policy: Optional[CircuitBreakerPolicy] = None,
    ) -> None:
        self.retry_policy = retry_policy or RetryPolicy()
        self.breaker_policy = breaker_policy or CircuitBreakerPolicy()
        self._breakers: Dict[str, CircuitBreaker] = {}

    def _breaker_for(self, key: str) -> CircuitBreaker:
        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker(self.breaker_policy)
        return self._breakers[key]

    def execute(self, key: str, fn: Callable[[], Any]) -> Any:
        breaker = self._breaker_for(key)
        if not breaker.allow():
            raise RuntimeError(f"Circuit breaker open for {key}")

        def _call():
            return fn()

        try:
            result = sync_retry_with_backoff(
                _call,
                max_retries=self.retry_policy.max_retries,
                base_delay=self.retry_policy.base_delay,
                max_delay=self.retry_policy.max_delay,
                exponential_base=self.retry_policy.exponential_base,
            )
            breaker.record_success()
            return result
        except Exception:
            breaker.record_failure()
            raise

    async def execute_async(self, key: str, fn: Callable[[], Any]) -> Any:
        breaker = self._breaker_for(key)
        if not breaker.allow():
            raise RuntimeError(f"Circuit breaker open for {key}")

        async def _call():
            return await fn()

        try:
            result = await retry_with_backoff(
                _call,
                max_retries=self.retry_policy.max_retries,
                base_delay=self.retry_policy.base_delay,
                max_delay=self.retry_policy.max_delay,
                exponential_base=self.retry_policy.exponential_base,
            )
            breaker.record_success()
            return result
        except Exception:
            breaker.record_failure()
            raise
