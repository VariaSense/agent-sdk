from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .messages import Message
from .tools import Tool
from agent_sdk.config.model_config import ModelConfig
from agent_sdk.config.rate_limit import RateLimiter
from agent_sdk.observability.bus import EventBus

@dataclass
class AgentContext:
    short_term: List[Message] = field(default_factory=list)
    long_term: List[Message] = field(default_factory=list)
    tools: Dict[str, Tool] = field(default_factory=dict)
    model_config: Optional[ModelConfig] = None
    config: Dict[str, Any] = field(default_factory=dict)
    events: Optional[EventBus] = None
    rate_limiter: Optional[RateLimiter] = None
