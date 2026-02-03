"""Multi-agent orchestrator for coordinating agent execution."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime
import uuid


class AgentExecutionMode(Enum):
    """Execution mode for multi-agent coordination."""
    
    PARALLEL = "parallel"          # All agents execute simultaneously
    SEQUENTIAL = "sequential"      # Agents execute one after another
    CASCADE = "cascade"            # Result of one feeds into next
    COMPETITIVE = "competitive"   # First successful result wins
    CONSENSUS = "consensus"       # Wait for agreement
    HIERARCHICAL = "hierarchical"  # Primary -> secondary fallback


@dataclass
class AgentDefinition:
    """Definition of an agent in the orchestrator."""
    
    agent_id: str
    name: str
    description: str = ""
    priority: int = 0
    capabilities: List[str] = field(default_factory=list)
    timeout_ms: float = 30000.0
    retry_count: int = 0
    required: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "capabilities": self.capabilities,
            "timeout_ms": self.timeout_ms,
            "retry_count": self.retry_count,
            "required": self.required,
            "metadata": self.metadata
        }


@dataclass
class AgentExecutionResult:
    """Result from a single agent execution."""
    
    agent_id: str
    success: bool
    output: Any = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    cost_incurred: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "success": self.success,
            "output": self.output,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "tokens_used": self.tokens_used,
            "cost_incurred": self.cost_incurred,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class MultiAgentResult:
    """Aggregated result from multi-agent execution."""
    
    session_id: str
    execution_mode: AgentExecutionMode
    agent_results: List[AgentExecutionResult] = field(default_factory=list)
    final_output: Any = None
    conflict_detected: bool = False
    conflict_resolution_applied: Optional[str] = None
    total_execution_time_ms: float = 0.0
    total_cost_incurred: float = 0.0
    total_tokens_used: int = 0
    success: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "execution_mode": self.execution_mode.value,
            "agent_results": [r.to_dict() for r in self.agent_results],
            "final_output": self.final_output,
            "conflict_detected": self.conflict_detected,
            "conflict_resolution_applied": self.conflict_resolution_applied,
            "total_execution_time_ms": self.total_execution_time_ms,
            "total_cost_incurred": self.total_cost_incurred,
            "total_tokens_used": self.total_tokens_used,
            "success": self.success,
            "metadata": self.metadata
        }


class MultiAgentOrchestrator:
    """Orchestrates execution of multiple agents."""
    
    def __init__(self, name: str = "default"):
        """Initialize orchestrator.
        
        Args:
            name: Orchestrator name
        """
        self.name = name
        self.agents: Dict[str, AgentDefinition] = {}
        self.execution_mode: AgentExecutionMode = AgentExecutionMode.PARALLEL
        self.timeout_ms: float = 60000.0
        self.metadata: Dict[str, Any] = {}
    
    def register_agent(self, agent: AgentDefinition) -> None:
        """Register an agent.
        
        Args:
            agent: Agent definition
        """
        self.agents[agent.agent_id] = agent
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent.
        
        Args:
            agent_id: ID of agent to unregister
        """
        if agent_id in self.agents:
            del self.agents[agent_id]
    
    def get_agent(self, agent_id: str) -> Optional[AgentDefinition]:
        """Get agent definition.
        
        Args:
            agent_id: ID of agent
        
        Returns:
            Agent definition or None
        """
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[AgentDefinition]:
        """List all registered agents.
        
        Returns:
            List of agent definitions
        """
        return list(self.agents.values())
    
    def validate_orchestrator(self) -> List[str]:
        """Validate orchestrator configuration.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not self.agents:
            errors.append("No agents registered")
        
        # Check required agents have higher priority
        required_agents = [a for a in self.agents.values() if a.required]
        optional_agents = [a for a in self.agents.values() if not a.required]
        
        if required_agents and optional_agents:
            req_min_priority = min(a.priority for a in required_agents)
            opt_max_priority = max(a.priority for a in optional_agents)
            if req_min_priority <= opt_max_priority:
                errors.append("Required agents should have higher priority than optional")
        
        return errors
    
    def create_session(self) -> str:
        """Create a new execution session.
        
        Returns:
            Session ID
        """
        return str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "execution_mode": self.execution_mode.value,
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "timeout_ms": self.timeout_ms,
            "metadata": self.metadata
        }
