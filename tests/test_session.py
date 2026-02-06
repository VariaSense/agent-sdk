"""Tests for session management."""

import pytest
from agent_sdk.coordination.session import (
    SessionStatus,
    AgentSessionSnapshot,
    AgentSession,
    SessionManager
)
from datetime import datetime, timezone


class TestAgentSessionSnapshot:
    """Tests for AgentSessionSnapshot."""
    
    def test_creation(self):
        """Test snapshot creation."""
        snapshot = AgentSessionSnapshot(
            agent_id="a1",
            agent_name="Agent 1",
            status="completed",
            result=42
        )
        
        assert snapshot.agent_id == "a1"
        assert snapshot.result == 42
        assert snapshot.status == "completed"
    
    def test_to_dict(self):
        """Test serialization."""
        snapshot = AgentSessionSnapshot(
            agent_id="a1",
            agent_name="Agent 1",
            status="completed",
            result=42,
            execution_time_ms=1000.0
        )
        
        d = snapshot.to_dict()
        
        assert d["agent_id"] == "a1"
        assert d["result"] == 42
        assert d["execution_time_ms"] == 1000.0
    
    def test_to_dict_with_times(self):
        """Test serialization with times."""
        now = datetime.now(timezone.utc)
        snapshot = AgentSessionSnapshot(
            agent_id="a1",
            agent_name="Agent 1",
            status="completed",
            start_time=now,
            end_time=now
        )
        
        d = snapshot.to_dict()
        
        assert d["start_time"] is not None
        assert d["end_time"] is not None


class TestAgentSession:
    """Tests for AgentSession."""
    
    def test_creation(self):
        """Test session creation."""
        session = AgentSession(
            session_id="s1",
            name="test_session"
        )
        
        assert session.session_id == "s1"
        assert session.status == SessionStatus.CREATED
        assert len(session.agent_snapshots) == 0
    
    def test_to_dict(self):
        """Test serialization."""
        session = AgentSession(
            session_id="s1",
            name="test_session"
        )
        
        d = session.to_dict()
        
        assert d["session_id"] == "s1"
        assert d["status"] == "created"
        assert len(d["agent_snapshots"]) == 0


class TestSessionManager:
    """Tests for SessionManager."""
    
    def test_initialization(self):
        """Test manager creation."""
        manager = SessionManager()
        
        assert len(manager.sessions) == 0
        assert len(manager.active_sessions) == 0
        assert len(manager.completed_sessions) == 0
    
    def test_create_session(self):
        """Test session creation."""
        manager = SessionManager()
        
        session = manager.create_session(name="test_session")
        
        assert session.session_id is not None
        assert session.name == "test_session"
        assert session.session_id in manager.sessions
    
    def test_create_session_with_metadata(self):
        """Test session creation with metadata."""
        manager = SessionManager()
        
        session = manager.create_session(
            name="test",
            metadata={"key": "value"},
            tags=["important"]
        )
        
        assert session.metadata == {"key": "value"}
        assert "important" in session.tags
    
    def test_get_session(self):
        """Test get session."""
        manager = SessionManager()
        
        session1 = manager.create_session(name="session1")
        session2 = manager.get_session(session1.session_id)
        
        assert session1.session_id == session2.session_id
    
    def test_get_nonexistent_session(self):
        """Test get non-existent session."""
        manager = SessionManager()
        
        session = manager.get_session("nonexistent")
        
        assert session is None
    
    def test_start_session(self):
        """Test start session."""
        manager = SessionManager()
        
        session = manager.create_session()
        started = manager.start_session(session.session_id)
        
        assert started.status == SessionStatus.STARTED
        assert started.started_at is not None
    
    def test_mark_executing(self):
        """Test mark executing."""
        manager = SessionManager()
        
        session = manager.create_session()
        executing = manager.mark_executing(session.session_id)
        
        assert executing.status == SessionStatus.EXECUTING
    
    def test_record_agent_result_success(self):
        """Test record successful result."""
        manager = SessionManager()
        
        session = manager.create_session()
        snapshot = manager.record_agent_result(
            session.session_id,
            agent_id="a1",
            agent_name="Agent 1",
            result=42,
            execution_time_ms=1000.0
        )
        
        assert snapshot.status == "completed"
        assert snapshot.result == 42
        
        # Check recorded in session
        updated_session = manager.get_session(session.session_id)
        assert "a1" in updated_session.agent_snapshots
    
    def test_record_agent_result_error(self):
        """Test record failed result."""
        manager = SessionManager()
        
        session = manager.create_session()
        snapshot = manager.record_agent_result(
            session.session_id,
            agent_id="a1",
            agent_name="Agent 1",
            error="Something failed"
        )
        
        assert snapshot.status == "failed"
        assert snapshot.error == "Something failed"
    
    def test_complete_session(self):
        """Test complete session."""
        manager = SessionManager()
        
        session = manager.create_session()
        completed = manager.complete_session(
            session.session_id,
            aggregated_result={"final": 42}
        )
        
        assert completed.status == SessionStatus.COMPLETED
        assert completed.aggregated_result == {"final": 42}
        assert session.session_id not in manager.active_sessions
        assert session.session_id in manager.completed_sessions
    
    def test_fail_session(self):
        """Test fail session."""
        manager = SessionManager()
        
        session = manager.create_session()
        failed = manager.fail_session(session.session_id, "Fatal error")
        
        assert failed.status == SessionStatus.FAILED
        assert failed.metadata["error"] == "Fatal error"
    
    def test_cancel_session(self):
        """Test cancel session."""
        manager = SessionManager()
        
        session = manager.create_session()
        cancelled = manager.cancel_session(session.session_id)
        
        assert cancelled.status == SessionStatus.CANCELLED
    
    def test_list_active_sessions(self):
        """Test list active sessions."""
        manager = SessionManager()
        
        s1 = manager.create_session()
        s2 = manager.create_session()
        manager.complete_session(s1.session_id)
        
        active = manager.list_active_sessions()
        
        assert len(active) == 1
        assert active[0].session_id == s2.session_id
    
    def test_list_completed_sessions(self):
        """Test list completed sessions."""
        manager = SessionManager()
        
        s1 = manager.create_session()
        s2 = manager.create_session()
        manager.complete_session(s1.session_id)
        manager.complete_session(s2.session_id)
        
        completed = manager.list_completed_sessions()
        
        assert len(completed) == 2
    
    def test_get_session_statistics(self):
        """Test session statistics."""
        manager = SessionManager()
        
        session = manager.create_session()
        manager.record_agent_result(
            session.session_id,
            agent_id="a1",
            agent_name="Agent 1",
            result=42,
            execution_time_ms=500.0,
            tokens_used=100,
            cost=1.5
        )
        manager.record_agent_result(
            session.session_id,
            agent_id="a2",
            agent_name="Agent 2",
            result=43,
            execution_time_ms=300.0,
            tokens_used=50,
            cost=0.75
        )
        
        stats = manager.get_session_statistics(session.session_id)
        
        assert stats["total_agents"] == 2
        assert stats["successful_agents"] == 2
        assert stats["total_execution_time_ms"] == 800.0
        assert stats["total_cost"] == 2.25
        assert stats["total_tokens"] == 150
    
    def test_get_session_statistics_with_failures(self):
        """Test statistics with failed agents."""
        manager = SessionManager()
        
        session = manager.create_session()
        manager.record_agent_result(
            session.session_id,
            agent_id="a1",
            agent_name="Agent 1",
            result=42
        )
        manager.record_agent_result(
            session.session_id,
            agent_id="a2",
            agent_name="Agent 2",
            error="Failed"
        )
        
        stats = manager.get_session_statistics(session.session_id)
        
        assert stats["total_agents"] == 2
        assert stats["successful_agents"] == 1
        assert stats["failed_agents"] == 1


class TestSessionStatusEnum:
    """Tests for SessionStatus enum."""
    
    def test_created_enum(self):
        """Test CREATED value."""
        assert SessionStatus.CREATED.value == "created"
    
    def test_started_enum(self):
        """Test STARTED value."""
        assert SessionStatus.STARTED.value == "started"
    
    def test_executing_enum(self):
        """Test EXECUTING value."""
        assert SessionStatus.EXECUTING.value == "executing"
    
    def test_completed_enum(self):
        """Test COMPLETED value."""
        assert SessionStatus.COMPLETED.value == "completed"
    
    def test_failed_enum(self):
        """Test FAILED value."""
        assert SessionStatus.FAILED.value == "failed"


class TestSessionEdgeCases:
    """Test edge cases."""
    
    def test_complete_nonexistent_session(self):
        """Test complete non-existent session."""
        manager = SessionManager()
        
        result = manager.complete_session("nonexistent")
        
        assert result is None
    
    def test_record_result_nonexistent_session(self):
        """Test record result to non-existent session."""
        manager = SessionManager()
        
        result = manager.record_agent_result(
            "nonexistent",
            agent_id="a1",
            agent_name="Agent 1",
            result=42
        )
        
        assert result is None
    
    def test_multiple_results_same_agent(self):
        """Test multiple results from same agent (overwrites)."""
        manager = SessionManager()
        
        session = manager.create_session()
        
        manager.record_agent_result(
            session.session_id,
            agent_id="a1",
            agent_name="Agent 1",
            result=42
        )
        
        manager.record_agent_result(
            session.session_id,
            agent_id="a1",
            agent_name="Agent 1",
            result=43
        )
        
        updated_session = manager.get_session(session.session_id)
        assert updated_session.agent_snapshots["a1"].result == 43
