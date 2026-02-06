"""Session management for multi-agent coordination."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone
import uuid


class SessionStatus(Enum):
    """Session lifecycle status."""
    
    CREATED = "created"
    STARTED = "started"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentSessionSnapshot:
    """Snapshot of agent execution in session."""
    
    agent_id: str
    agent_name: str
    status: str = "pending"  # pending, executing, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    cost: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "execution_time_ms": self.execution_time_ms,
            "tokens_used": self.tokens_used,
            "cost": self.cost
        }


@dataclass
class AgentSession:
    """Session for multi-agent execution."""
    
    session_id: str
    name: str = "default"
    status: SessionStatus = SessionStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Execution tracking
    agent_snapshots: Dict[str, AgentSessionSnapshot] = field(default_factory=dict)
    execution_mode: str = "parallel"
    total_execution_time_ms: float = 0.0
    
    # Results
    aggregated_result: Optional[Any] = None
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "name": self.name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "agent_snapshots": {
                agent_id: snapshot.to_dict()
                for agent_id, snapshot in self.agent_snapshots.items()
            },
            "execution_mode": self.execution_mode,
            "total_execution_time_ms": self.total_execution_time_ms,
            "aggregated_result": self.aggregated_result,
            "conflicts": self.conflicts,
            "metadata": self.metadata,
            "tags": self.tags
        }


class SessionManager:
    """Manages multi-agent sessions."""
    
    def __init__(self):
        """Initialize session manager."""
        self.sessions: Dict[str, AgentSession] = {}
        self.active_sessions: List[str] = []
        self.completed_sessions: List[str] = []
    
    def create_session(
        self,
        name: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> AgentSession:
        """Create new session.
        
        Args:
            name: Session name
            metadata: Additional metadata
            tags: Session tags
        
        Returns:
            New session
        """
        session_id = str(uuid.uuid4())
        
        session = AgentSession(
            session_id=session_id,
            name=name,
            metadata=metadata or {},
            tags=tags or []
        )
        
        self.sessions[session_id] = session
        self.active_sessions.append(session_id)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get session by ID.
        
        Args:
            session_id: Session ID
        
        Returns:
            Session or None
        """
        return self.sessions.get(session_id)
    
    def start_session(self, session_id: str) -> Optional[AgentSession]:
        """Start session.
        
        Args:
            session_id: Session ID
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        session.status = SessionStatus.STARTED
        session.started_at = datetime.now(timezone.utc)
        
        return session
    
    def mark_executing(self, session_id: str) -> Optional[AgentSession]:
        """Mark session as executing.
        
        Args:
            session_id: Session ID
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        session.status = SessionStatus.EXECUTING
        return session
    
    def record_agent_result(
        self,
        session_id: str,
        agent_id: str,
        agent_name: str,
        result: Any = None,
        error: Optional[str] = None,
        execution_time_ms: float = 0.0,
        tokens_used: int = 0,
        cost: float = 0.0
    ) -> Optional[AgentSessionSnapshot]:
        """Record agent execution result.
        
        Args:
            session_id: Session ID
            agent_id: Agent ID
            agent_name: Agent name
            result: Execution result
            error: Error message if failed
            execution_time_ms: Execution time
            tokens_used: Tokens used
            cost: Cost incurred
        
        Returns:
            Snapshot or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        status = "failed" if error else "completed"
        
        snapshot = AgentSessionSnapshot(
            agent_id=agent_id,
            agent_name=agent_name,
            status=status,
            result=result,
            error=error,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            cost=cost
        )
        
        session.agent_snapshots[agent_id] = snapshot
        session.total_execution_time_ms += execution_time_ms
        
        return snapshot
    
    def complete_session(
        self,
        session_id: str,
        aggregated_result: Optional[Any] = None,
        conflicts: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[AgentSession]:
        """Mark session as completed.
        
        Args:
            session_id: Session ID
            aggregated_result: Final aggregated result
            conflicts: Resolved conflicts
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        session.status = SessionStatus.COMPLETED
        session.completed_at = datetime.now(timezone.utc)
        session.aggregated_result = aggregated_result
        if conflicts:
            session.conflicts = conflicts
        
        if session_id in self.active_sessions:
            self.active_sessions.remove(session_id)
        self.completed_sessions.append(session_id)
        
        return session
    
    def fail_session(
        self,
        session_id: str,
        error: str
    ) -> Optional[AgentSession]:
        """Mark session as failed.
        
        Args:
            session_id: Session ID
            error: Error message
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        session.status = SessionStatus.FAILED
        session.completed_at = datetime.now(timezone.utc)
        session.metadata["error"] = error
        
        if session_id in self.active_sessions:
            self.active_sessions.remove(session_id)
        self.completed_sessions.append(session_id)
        
        return session
    
    def cancel_session(self, session_id: str) -> Optional[AgentSession]:
        """Cancel session.
        
        Args:
            session_id: Session ID
        
        Returns:
            Updated session or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        session.status = SessionStatus.CANCELLED
        session.completed_at = datetime.now(timezone.utc)
        
        if session_id in self.active_sessions:
            self.active_sessions.remove(session_id)
        self.completed_sessions.append(session_id)
        
        return session
    
    def list_active_sessions(self) -> List[AgentSession]:
        """Get all active sessions.
        
        Returns:
            List of active sessions
        """
        return [
            self.sessions[sid]
            for sid in self.active_sessions
            if sid in self.sessions
        ]
    
    def list_completed_sessions(self) -> List[AgentSession]:
        """Get all completed sessions.
        
        Returns:
            List of completed sessions
        """
        return [
            self.sessions[sid]
            for sid in self.completed_sessions
            if sid in self.sessions
        ]
    
    def get_session_statistics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session statistics.
        
        Args:
            session_id: Session ID
        
        Returns:
            Statistics or None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        total_cost = sum(
            snapshot.cost
            for snapshot in session.agent_snapshots.values()
        )
        total_tokens = sum(
            snapshot.tokens_used
            for snapshot in session.agent_snapshots.values()
        )
        successful_agents = sum(
            1 for snapshot in session.agent_snapshots.values()
            if snapshot.status == "completed"
        )
        
        return {
            "session_id": session_id,
            "status": session.status.value,
            "total_agents": len(session.agent_snapshots),
            "successful_agents": successful_agents,
            "failed_agents": len(session.agent_snapshots) - successful_agents,
            "total_execution_time_ms": session.total_execution_time_ms,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "average_agent_time_ms": (
                session.total_execution_time_ms / len(session.agent_snapshots)
                if session.agent_snapshots else 0.0
            )
        }
