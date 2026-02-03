"""Multi-agent coordination module.

This module provides distributed execution framework for coordinating
multiple agents in parallel, managing inter-agent communication, result
aggregation, and conflict resolution.

Classes:
    MultiAgentOrchestrator: Orchestrate multiple agents
    AgentMessageBus: Message bus for agent communication
    ResultAggregator: Aggregate results from multiple agents
    ConflictResolver: Resolve conflicts between results
    AgentSession: Track agent execution session

Usage:
    from agent_sdk.coordination import MultiAgentOrchestrator
    
    orchestrator = MultiAgentOrchestrator()
    orchestrator.register_agent(agent)
    result = await orchestrator.execute(task)
"""

from agent_sdk.coordination.orchestrator import (
    AgentExecutionMode,
    AgentDefinition,
    AgentExecutionResult,
    MultiAgentResult,
    MultiAgentOrchestrator
)
from agent_sdk.coordination.message_bus import (
    MessagePriority,
    MessageType,
    Message,
    AgentMessageBus
)
from agent_sdk.coordination.aggregator import (
    AggregationStrategy,
    AggregationResult,
    ResultAggregator
)
from agent_sdk.coordination.conflict_resolver import (
    ConflictResolutionStrategy,
    Conflict,
    AgentResult,
    ConflictAnalyzer,
    ConflictResolver
)
from agent_sdk.coordination.session import (
    SessionStatus,
    AgentSessionSnapshot,
    AgentSession,
    SessionManager
)

__all__ = [
    "AgentExecutionMode",
    "AgentDefinition",
    "AgentExecutionResult",
    "MultiAgentResult",
    "MultiAgentOrchestrator",
    "MessagePriority",
    "MessageType",
    "Message",
    "AgentMessageBus",
    "AggregationStrategy",
    "AggregationResult",
    "ResultAggregator",
    "ConflictResolutionStrategy",
    "Conflict",
    "AgentResult",
    "ConflictAnalyzer",
    "ConflictResolver",
    "SessionStatus",
    "AgentSessionSnapshot",
    "AgentSession",
    "SessionManager"
]
