from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from collections import defaultdict, deque
import time

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

    def _key(self, rule: RateLimitRule, agent: str, model: str, tenant: str) -> str:
        if rule.scope == "model":
            return f"model:{model}"
        if rule.scope == "agent":
            return f"agent:{agent}"
        if rule.scope == "tenant":
            return f"tenant:{tenant}"
        return "global"

    def check(self, agent: str, model: str, tokens: int, tenant: str = "default"):
        now = time.time()
        for rule in self.rules:
            key = self._key(rule, agent, model, tenant)

            while self.call_history[key] and now - self.call_history[key][0] > rule.window_seconds:
                self.call_history[key].popleft()
            while self.token_history[key] and now - self.token_history[key][0][0] > rule.window_seconds:
                self.token_history[key].popleft()

            if rule.max_calls is not None and len(self.call_history[key]) >= rule.max_calls:
                raise Exception(f"Rate limit exceeded: {rule.name} (calls)")

            if rule.max_tokens is not None:
                used = sum(t for _, t in self.token_history[key])
                if used + tokens > rule.max_tokens:
                    raise Exception(f"Rate limit exceeded: {rule.name} (tokens)")

        for rule in self.rules:
            key = self._key(rule, agent, model, tenant)
            self.call_history[key].append(now)
            self.token_history[key].append((now, tokens))
