from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from collections import defaultdict, deque
import time
from threading import Lock
import logging

logger = logging.getLogger(__name__)

@dataclass
class RateLimitRule:
    name: str
    max_calls: Optional[int] = None
    max_tokens: Optional[int] = None
    window_seconds: int = 60
    scope: str = "model"  # "model", "agent", "tenant"

class RateLimiter:
    def __init__(
        self,
        rules: Optional[List[RateLimitRule]] = None,
        max_requests: Optional[int] = None,
        window_seconds: int = 60,
    ):
        if rules is None:
            if max_requests is None:
                rules = []
            else:
                rules = [
                    RateLimitRule(
                        name="default",
                        max_calls=max_requests,
                        window_seconds=window_seconds,
                        scope="global",
                    )
                ]

        self.rules = rules
        self.call_history: Dict[str, deque] = defaultdict(deque)
        self.token_history: Dict[str, deque[Tuple[float, int]]] = defaultdict(deque)
        self._lock = Lock()  # Thread safety for concurrent access

    def _key(self, rule: RateLimitRule, agent: str, model: str, tenant: str) -> str:
        if rule.scope == "model":
            return f"model:{model}"
        if rule.scope == "agent":
            return f"agent:{agent}"
        if rule.scope == "tenant":
            return f"tenant:{tenant}"
        return "global"

    def check(
        self,
        agent: str = "default",
        model: str = "default",
        tokens: int = 0,
        tenant: str = "default",
    ) -> bool:
        """Check if rate limits are exceeded and record the usage
        
        Args:
            agent: Agent name
            model: Model name
            tokens: Number of tokens being used
            tenant: Tenant ID (for multi-tenancy)
            
        Raises:
            RateLimitError: If any rate limit is exceeded
        """
        from agent_sdk.exceptions import RateLimitError
        
        if not self.rules:
            return True

        with self._lock:  # Thread-safe operation
            now = time.time()
            
            # Clean up old entries and check limits
            for rule in self.rules:
                key = self._key(rule, agent, model, tenant)

                # Clean old call history
                while self.call_history[key] and now - self.call_history[key][0] > rule.window_seconds:
                    self.call_history[key].popleft()
                
                # Clean old token history
                while self.token_history[key] and now - self.token_history[key][0][0] > rule.window_seconds:
                    self.token_history[key].popleft()

                # Check call limit
                if rule.max_calls is not None and len(self.call_history[key]) >= rule.max_calls:
                    logger.warning(
                        f"Rate limit exceeded for {rule.name} (calls): "
                        f"{len(self.call_history[key])}/{rule.max_calls}"
                    )
                    raise RateLimitError(
                        f"Rate limit exceeded: {rule.name} (calls)",
                        code="RATE_LIMIT_CALLS"
                    )

                # Check token limit
                if rule.max_tokens is not None:
                    used = sum(t for _, t in self.token_history[key])
                    if used + tokens > rule.max_tokens:
                        logger.warning(
                            f"Rate limit exceeded for {rule.name} (tokens): "
                            f"{used + tokens}/{rule.max_tokens}"
                        )
                        raise RateLimitError(
                            f"Rate limit exceeded: {rule.name} (tokens)",
                            code="RATE_LIMIT_TOKENS"
                        )

            # Record the usage
            for rule in self.rules:
                key = self._key(rule, agent, model, tenant)
                self.call_history[key].append(now)
                self.token_history[key].append((now, tokens))

        return True

    def reset(self) -> None:
        """Reset all rate limit state."""
        with self._lock:
            self.call_history.clear()
            self.token_history.clear()

    def _primary_rule(self) -> Optional[RateLimitRule]:
        return self.rules[0] if self.rules else None

    def get_remaining(
        self, agent: str = "default", model: str = "default", tenant: str = "default"
    ) -> Optional[int]:
        """Get remaining calls for the primary rule."""
        rule = self._primary_rule()
        if rule is None or rule.max_calls is None:
            return None
        key = self._key(rule, agent, model, tenant)
        with self._lock:
            now = time.time()
            while self.call_history[key] and now - self.call_history[key][0] > rule.window_seconds:
                self.call_history[key].popleft()
            remaining = rule.max_calls - len(self.call_history[key])
            return max(0, remaining)

    def get_status(
        self, agent: str = "default", model: str = "default", tenant: str = "default"
    ) -> Dict[str, Optional[int]]:
        """Get status for the primary rule."""
        rule = self._primary_rule()
        max_requests = rule.max_calls if rule else None
        window_seconds = rule.window_seconds if rule else None
        remaining = self.get_remaining(agent=agent, model=model, tenant=tenant)
        current_requests = None
        if rule is not None:
            key = self._key(rule, agent, model, tenant)
            current_requests = len(self.call_history[key])

        return {
            "max_requests": max_requests,
            "window_seconds": window_seconds,
            "current_requests": current_requests,
            "remaining": remaining,
        }
