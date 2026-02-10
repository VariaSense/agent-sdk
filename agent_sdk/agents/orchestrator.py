"""
Multi-Agent Orchestration Framework

Enables coordination between multiple agents with:
- Agent registry and lifecycle management
- Message routing between agents
- Shared context management
- Consensus algorithms
- Performance monitoring
- Agent communication protocol

Allows building complex multi-agent systems for collaborative problem solving.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Set
import logging
import json


logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of messages between agents."""

    REQUEST = "request"
    RESPONSE = "response"
    BROADCAST = "broadcast"
    CONSENSUS_PROPOSAL = "consensus_proposal"
    CONSENSUS_VOTE = "consensus_vote"
    CONTEXT_UPDATE = "context_update"
    ERROR = "error"
    CANCEL = "cancel"


class AgentRole(str, Enum):
    """Roles in multi-agent system."""

    WORKER = "worker"
    COORDINATOR = "coordinator"
    ARBITER = "arbiter"
    OBSERVER = "observer"


class ConsensusAlgorithm(str, Enum):
    """Consensus algorithms for agent agreement."""

    MAJORITY = "majority"  # > 50%
    UNANIMOUS = "unanimous"  # 100%
    WEIGHTED = "weighted"  # Based on agent weights
    QUORUM = "quorum"  # Minimum percentage


class TaskStatus(str, Enum):
    """Hierarchical task status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELED = "canceled"


@dataclass
class TaskNode:
    task_id: str
    parent_id: Optional[str]
    assigned_agents: List[str]
    status: TaskStatus = TaskStatus.PENDING
    children: Set[str] = field(default_factory=set)


@dataclass
class Message:
    """
    Inter-agent message.

    Attributes:
        message_id: Unique message identifier
        sender_id: ID of sending agent
        recipients: List of recipient agent IDs
        message_type: Type of message
        content: Message content/payload
        timestamp: When message was sent
        priority: Message priority
    """

    message_id: str
    sender_id: str
    recipients: List[str]
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0  # Higher = higher priority

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "recipients": self.recipients,
            "message_type": self.message_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority,
        }

    @staticmethod
    def create_request(
        sender_id: str, recipients: List[str], content: Dict[str, Any]
    ) -> "Message":
        """Create a request message."""
        import uuid

        return Message(
            message_id=str(uuid.uuid4())[:8],
            sender_id=sender_id,
            recipients=recipients,
            message_type=MessageType.REQUEST,
            content=content,
        )

    @staticmethod
    def create_response(
        sender_id: str,
        recipient_id: str,
        content: Dict[str, Any],
        priority: int = 0,
    ) -> "Message":
        """Create a response message."""
        import uuid

        return Message(
            message_id=str(uuid.uuid4())[:8],
            sender_id=sender_id,
            recipients=[recipient_id],
            message_type=MessageType.RESPONSE,
            content=content,
            priority=priority,
        )


@dataclass
class SharedContext:
    """
    Shared context accessible to all agents.

    Stores shared state, goals, and information accessible across agents.
    """

    context_id: str
    shared_data: Dict[str, Any] = field(default_factory=dict)
    global_goal: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_log: List[Dict[str, Any]] = field(default_factory=list)

    def set_data(self, key: str, value: Any, agent_id: str) -> None:
        """Set shared data."""
        self.shared_data[key] = value
        self.updated_at = datetime.now()
        self.access_log.append(
            {
                "action": "set",
                "key": key,
                "agent_id": agent_id,
                "timestamp": self.updated_at.isoformat(),
            }
        )

    def get_data(self, key: str, agent_id: str) -> Any:
        """Get shared data."""
        self.access_log.append(
            {
                "action": "get",
                "key": key,
                "agent_id": agent_id,
                "timestamp": datetime.now().isoformat(),
            }
        )
        return self.shared_data.get(key)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "context_id": self.context_id,
            "shared_data": self.shared_data,
            "global_goal": self.global_goal,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class AgentState:
    """State of an agent in the system."""

    agent_id: str
    name: str
    role: AgentRole
    status: str = "idle"  # idle, working, error
    current_task: Optional[str] = None
    last_heartbeat: datetime = field(default_factory=datetime.now)
    performance_score: float = 1.0
    message_count: int = 0
    error_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "status": self.status,
            "current_task": self.current_task,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "performance_score": self.performance_score,
            "message_count": self.message_count,
            "error_count": self.error_count,
        }


class MessageRouter:
    """
    Routes messages between agents.

    Manages message queues and delivers messages to appropriate agents.
    """

    def __init__(self):
        """Initialize message router."""
        self.message_queues: Dict[str, List[Message]] = {}
        self.message_history: List[Message] = []

    def register_agent(self, agent_id: str) -> None:
        """Register an agent to receive messages."""
        if agent_id not in self.message_queues:
            self.message_queues[agent_id] = []

    def send_message(self, message: Message) -> None:
        """
        Send a message.

        Routes to recipients and stores in history.
        """
        self.message_history.append(message)

        for recipient in message.recipients:
            if recipient in self.message_queues:
                self.message_queues[recipient].append(message)
            else:
                logger.warning(f"Recipient not found: {recipient}")

        logger.debug(f"Message routed: {message.sender_id} → {message.recipients}")

    def get_messages(self, agent_id: str) -> List[Message]:
        """Get all pending messages for an agent."""
        if agent_id not in self.message_queues:
            return []
        messages = self.message_queues[agent_id]
        self.message_queues[agent_id] = []
        return messages

    def broadcast_message(
        self,
        sender_id: str,
        recipients: List[str],
        content: Dict[str, Any],
        exclude_sender: bool = True,
    ) -> None:
        """Broadcast a message to multiple agents."""
        actual_recipients = recipients
        if exclude_sender and sender_id in actual_recipients:
            actual_recipients = [r for r in actual_recipients if r != sender_id]

        message = Message(
            message_id=f"broadcast_{len(self.message_history)}",
            sender_id=sender_id,
            recipients=actual_recipients,
            message_type=MessageType.BROADCAST,
            content=content,
        )
        self.send_message(message)


class ConsensusVote:
    """Tracks votes for consensus."""

    def __init__(self, proposal_id: str, algorithm: ConsensusAlgorithm):
        """Initialize consensus vote."""
        self.proposal_id = proposal_id
        self.algorithm = algorithm
        self.votes: Dict[str, bool] = {}
        self.weights: Dict[str, float] = {}

    def cast_vote(self, agent_id: str, vote: bool, weight: float = 1.0) -> None:
        """Cast a vote."""
        self.votes[agent_id] = vote
        self.weights[agent_id] = weight

    def get_result(self, min_participants: int = 1) -> bool:
        """Determine consensus result."""
        if len(self.votes) < min_participants:
            return False

        if self.algorithm == ConsensusAlgorithm.MAJORITY:
            yes_count = sum(1 for v in self.votes.values() if v)
            return yes_count > len(self.votes) / 2

        elif self.algorithm == ConsensusAlgorithm.UNANIMOUS:
            return all(self.votes.values())

        elif self.algorithm == ConsensusAlgorithm.WEIGHTED:
            yes_weight = sum(
                self.weights[aid] for aid, v in self.votes.items() if v
            )
            total_weight = sum(self.weights.values())
            return yes_weight > total_weight / 2

        elif self.algorithm == ConsensusAlgorithm.QUORUM:
            participation = len(self.votes) / (max(self.weights.values()) or 1)
            yes_count = sum(1 for v in self.votes.values() if v)
            return participation >= 0.5 and yes_count > len(self.votes) / 2

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "algorithm": self.algorithm.value,
            "total_votes": len(self.votes),
            "yes_votes": sum(1 for v in self.votes.values() if v),
            "no_votes": sum(1 for v in self.votes.values() if not v),
        }


class MultiAgentOrchestrator:
    """
    Orchestrates multiple agents working together.

    Manages agent registry, messaging, context, and coordination.
    """

    def __init__(self, system_id: str = "multi-agent-system"):
        """Initialize orchestrator."""
        self.system_id = system_id
        self.agents: Dict[str, AgentState] = {}
        self.router = MessageRouter()
        self.shared_context: Optional[SharedContext] = None
        self.active_consensus: Dict[str, ConsensusVote] = {}
        self.tasks: Dict[str, TaskNode] = {}
        self.created_at = datetime.now()

    def register_agent(
        self, agent_id: str, name: str, role: AgentRole
    ) -> AgentState:
        """
        Register a new agent.

        Args:
            agent_id: Unique agent identifier
            name: Human-readable name
            role: Agent role in system

        Returns:
            AgentState
        """
        agent_state = AgentState(agent_id=agent_id, name=name, role=role)
        self.agents[agent_id] = agent_state
        self.router.register_agent(agent_id)
        logger.info(f"Registered agent: {agent_id} ({name})")
        return agent_state

    def create_shared_context(self, global_goal: Optional[str] = None) -> SharedContext:
        """
        Create shared context for all agents.

        Args:
            global_goal: Overall system goal

        Returns:
            SharedContext
        """
        import uuid

        context_id = str(uuid.uuid4())[:8]
        self.shared_context = SharedContext(
            context_id=context_id, global_goal=global_goal
        )
        logger.info(f"Created shared context: {context_id}")
        return self.shared_context

    def create_task(self, task_id: str, assigned_agents: List[str], parent_id: Optional[str] = None) -> TaskNode:
        """Register a hierarchical task."""
        node = TaskNode(task_id=task_id, parent_id=parent_id, assigned_agents=assigned_agents)
        self.tasks[task_id] = node
        if parent_id and parent_id in self.tasks:
            self.tasks[parent_id].children.add(task_id)
        return node

    def set_task_status(self, task_id: str, status: TaskStatus) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].status = status

    def cancel_task(self, task_id: str, reason: str = "canceled") -> None:
        """Cancel a task and propagate to children."""
        node = self.tasks.get(task_id)
        if not node:
            return
        node.status = TaskStatus.CANCELED
        if node.assigned_agents:
            self.send_message(
                "system",
                node.assigned_agents,
                MessageType.CANCEL,
                {"task_id": task_id, "reason": reason},
            )
        for child_id in list(node.children):
            self.cancel_task(child_id, reason=reason)

    def send_message(
        self,
        sender_id: str,
        recipients: List[str],
        message_type: MessageType,
        content: Dict[str, Any],
    ) -> None:
        """Send a message between agents."""
        import uuid

        message = Message(
            message_id=str(uuid.uuid4())[:8],
            sender_id=sender_id,
            recipients=recipients,
            message_type=message_type,
            content=content,
        )
        self.router.send_message(message)

        if sender_id in self.agents:
            self.agents[sender_id].message_count += 1

    def propose_consensus(
        self,
        proposal_id: str,
        algorithm: ConsensusAlgorithm,
        affected_agents: List[str],
    ) -> ConsensusVote:
        """
        Propose a consensus decision.

        Args:
            proposal_id: Unique proposal identifier
            algorithm: Consensus algorithm to use
            affected_agents: Agents that should vote

        Returns:
            ConsensusVote object
        """
        vote = ConsensusVote(proposal_id, algorithm)
        self.active_consensus[proposal_id] = vote

        # Notify agents
        self.send_message(
            "system",
            affected_agents,
            MessageType.CONSENSUS_PROPOSAL,
            {"proposal_id": proposal_id, "algorithm": algorithm.value},
        )

        logger.info(f"Proposed consensus: {proposal_id}")
        return vote

    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        return {
            "total_agents": len(self.agents),
            "agents": {
                agent_id: agent.to_dict()
                for agent_id, agent in self.agents.items()
            },
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        agent_statuses = [agent.status for agent in self.agents.values()]
        working_agents = sum(1 for s in agent_statuses if s == "working")

        return {
            "system_id": self.system_id,
            "uptime": (datetime.now() - self.created_at).total_seconds(),
            "total_agents": len(self.agents),
            "working_agents": working_agents,
            "idle_agents": sum(1 for s in agent_statuses if s == "idle"),
            "failed_agents": sum(1 for s in agent_statuses if s == "error"),
            "message_history_size": len(self.router.message_history),
            "shared_context": (
                self.shared_context.to_dict() if self.shared_context else None
            ),
            "active_consensus": len(self.active_consensus),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "system_id": self.system_id,
            "created_at": self.created_at.isoformat(),
            "agent_count": len(self.agents),
            "status": self.get_system_status(),
            "agents": {
                agent_id: agent.to_dict()
                for agent_id, agent in self.agents.items()
            },
        }


def create_multi_agent_system(system_id: str = "multi-agent-system") -> MultiAgentOrchestrator:
    """
    Factory function to create multi-agent system.

    Args:
        system_id: Identifier for the system

    Returns:
        MultiAgentOrchestrator
    """
    return MultiAgentOrchestrator(system_id)


__all__ = [
    "MessageType",
    "AgentRole",
    "ConsensusAlgorithm",
    "Message",
    "SharedContext",
    "AgentState",
    "MessageRouter",
    "ConsensusVote",
    "MultiAgentOrchestrator",
    "create_multi_agent_system",
]
