"""Message bus for inter-agent communication."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
from datetime import datetime
import uuid


class MessagePriority(Enum):
    """Message priority levels."""
    
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class MessageType(Enum):
    """Types of messages between agents."""
    
    QUERY = "query"           # Agent asking for information
    RESPONSE = "response"     # Response to a query
    DIRECTIVE = "directive"   # Instruction to perform action
    STATUS = "status"         # Status update
    ERROR = "error"          # Error notification
    HEARTBEAT = "heartbeat"  # Keep-alive signal


@dataclass
class Message:
    """Message for inter-agent communication."""
    
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.QUERY
    source_agent_id: str = ""
    target_agent_id: Optional[str] = None  # None = broadcast
    payload: Any = None
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reply_to: Optional[str] = None  # For message threading
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "source_agent_id": self.source_agent_id,
            "target_agent_id": self.target_agent_id,
            "payload": self.payload,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
            "metadata": self.metadata
        }
    
    def is_broadcast(self) -> bool:
        """Check if message is broadcast."""
        return self.target_agent_id is None
    
    def is_directed(self) -> bool:
        """Check if message is directed to specific agent."""
        return self.target_agent_id is not None


class AgentMessageBus:
    """Message bus for inter-agent communication."""
    
    def __init__(self, max_queue_size: int = 1000):
        """Initialize message bus.
        
        Args:
            max_queue_size: Maximum messages to queue
        """
        self.max_queue_size = max_queue_size
        self.message_queue: List[Message] = []
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.message_history: List[Message] = []
        self.agent_subscriptions: Dict[str, List[MessageType]] = {}
    
    def subscribe(
        self,
        agent_id: str,
        message_types: Optional[List[MessageType]] = None
    ) -> None:
        """Subscribe agent to message types.
        
        Args:
            agent_id: Agent to subscribe
            message_types: Message types to receive (None = all)
        """
        if message_types is None:
            message_types = list(MessageType)
        self.agent_subscriptions[agent_id] = message_types
    
    def unsubscribe(self, agent_id: str) -> None:
        """Unsubscribe agent from all messages.
        
        Args:
            agent_id: Agent to unsubscribe
        """
        if agent_id in self.agent_subscriptions:
            del self.agent_subscriptions[agent_id]
    
    def register_handler(
        self,
        message_type: MessageType,
        handler: Callable[[Message], None]
    ) -> None:
        """Register handler for message type.
        
        Args:
            message_type: Type of message
            handler: Handler function
        """
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)
    
    def publish(self, message: Message) -> bool:
        """Publish message to bus.
        
        Args:
            message: Message to publish
        
        Returns:
            True if published successfully
        """
        if len(self.message_queue) >= self.max_queue_size:
            return False
        
        self.message_queue.append(message)
        self.message_history.append(message)
        return True
    
    def get_messages(
        self,
        agent_id: str,
        message_type: Optional[MessageType] = None
    ) -> List[Message]:
        """Get messages for agent.
        
        Args:
            agent_id: Agent ID
            message_type: Filter by type (optional)
        
        Returns:
            List of messages
        """
        if agent_id not in self.agent_subscriptions:
            return []
        
        subscribed_types = self.agent_subscriptions[agent_id]
        messages = []
        
        for msg in self.message_queue:
            # Check if directed to this agent or broadcast
            if msg.target_agent_id and msg.target_agent_id != agent_id:
                continue
            
            # Check if subscribed to this type
            if msg.message_type not in subscribed_types:
                continue
            
            # Filter by type if specified
            if message_type and msg.message_type != message_type:
                continue
            
            messages.append(msg)
        
        return messages
    
    def consume_message(self, message_id: str) -> Optional[Message]:
        """Remove message from queue after consumption.
        
        Args:
            message_id: Message ID to consume
        
        Returns:
            Message or None if not found
        """
        for i, msg in enumerate(self.message_queue):
            if msg.message_id == message_id:
                self.message_queue.pop(i)
                return msg
        return None
    
    def clear_queue(self) -> int:
        """Clear all pending messages.
        
        Returns:
            Number of messages cleared
        """
        count = len(self.message_queue)
        self.message_queue = []
        return count
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics.
        
        Returns:
            Queue statistics
        """
        return {
            "queue_size": len(self.message_queue),
            "max_queue_size": self.max_queue_size,
            "queue_utilization": len(self.message_queue) / self.max_queue_size,
            "total_messages_published": len(self.message_history),
            "subscribed_agents": len(self.agent_subscriptions)
        }
