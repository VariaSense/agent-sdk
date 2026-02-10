from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .messages import Message
from .tools import Tool
from agent_sdk.config.model_config import ModelConfig
from agent_sdk.config.rate_limit import RateLimiter
from agent_sdk.observability.bus import EventBus

# Configuration for memory limits
DEFAULT_MAX_SHORT_TERM_MESSAGES = 1000
DEFAULT_MAX_LONG_TERM_MESSAGES = 10000


@dataclass
class AgentContext:
    short_term: List[Message] = field(default_factory=list)
    long_term: List[Message] = field(default_factory=list)
    tools: Dict[str, Tool] = field(default_factory=dict)
    model_config: Optional[ModelConfig] = None
    config: Dict[str, Any] = field(default_factory=dict)
    events: Optional[EventBus] = None
    rate_limiter: Optional[RateLimiter] = None
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    org_id: Optional[str] = None
    
    # Memory management settings
    max_short_term: int = DEFAULT_MAX_SHORT_TERM_MESSAGES
    max_long_term: int = DEFAULT_MAX_LONG_TERM_MESSAGES

    def set_run_context(
        self,
        session_id: Optional[str],
        run_id: Optional[str],
        org_id: Optional[str] = None,
    ) -> None:
        """Set run/session identifiers for this context."""
        if session_id is not None:
            self.session_id = session_id
        if run_id is not None:
            self.run_id = run_id
        if org_id is not None:
            self.org_id = org_id

    def apply_run_metadata(self, message: Message) -> None:
        """Attach run/session identifiers to a message if available."""
        if self.session_id:
            message.metadata.setdefault("session_id", self.session_id)
        if self.run_id:
            message.metadata.setdefault("run_id", self.run_id)

    def add_short_term_message(self, message: Message):
        """Add message to short-term memory with retention limit
        
        Args:
            message: Message to add
        """
        self.short_term.append(message)
        
        # Keep only the most recent messages
        if len(self.short_term) > self.max_short_term:
            removed = len(self.short_term) - self.max_short_term
            self.short_term = self.short_term[-self.max_short_term:]
            import logging
            logging.getLogger(__name__).debug(
                f"Removed {removed} old short-term messages (limit: {self.max_short_term})"
            )

    def add_long_term_message(self, message: Message):
        """Add message to long-term memory with retention limit
        
        Args:
            message: Message to add
        """
        self.long_term.append(message)
        
        # Keep only the most recent messages
        if len(self.long_term) > self.max_long_term:
            removed = len(self.long_term) - self.max_long_term
            self.long_term = self.long_term[-self.max_long_term:]
            import logging
            logging.getLogger(__name__).debug(
                f"Removed {removed} old long-term messages (limit: {self.max_long_term})"
            )

    def cleanup_old_messages(self, keep_count: Optional[int] = None):
        """Manually clean up old messages
        
        Args:
            keep_count: Number of messages to keep (uses max limits if not specified)
        """
        if keep_count is None:
            keep_count = self.max_short_term
        
        if len(self.short_term) > keep_count:
            self.short_term = self.short_term[-keep_count:]
        if len(self.long_term) > keep_count:
            self.long_term = self.long_term[-keep_count:]
        
        import logging
        logging.getLogger(__name__).debug("Cleaned up old messages from context")
