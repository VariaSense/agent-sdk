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
    def __init__(self, rules: List[RateLimitRule]):
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

    def check(self, agent: str, model: str, tokens: int, tenant: str = "default"):
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
