"""Tests for human-in-the-loop module."""

import pytest
import asyncio
from agent_sdk.human_in_the_loop.feedback import FeedbackType, HumanFeedback, FeedbackCollector
from agent_sdk.human_in_the_loop.approval import ApprovalStatus, ApprovalRequest, ApprovalWorkflow
from agent_sdk.human_in_the_loop.agent import HumanInTheLoopAgent


class TestHumanFeedback:
    """Test HumanFeedback class."""
    
    def test_create_feedback(self):
        """Test creating feedback."""
        feedback = HumanFeedback(
            decision_id="dec-123",
            feedback_type=FeedbackType.POSITIVE,
            content="Great decision!",
            rating=5,
        )
        assert feedback.decision_id == "dec-123"
        assert feedback.feedback_type == FeedbackType.POSITIVE
        assert feedback.rating == 5
    
    def test_feedback_is_positive(self):
        """Test positive feedback detection."""
        pos_feedback = HumanFeedback(feedback_type=FeedbackType.POSITIVE, rating=5)
        assert pos_feedback.is_positive() is True
        
        neg_feedback = HumanFeedback(feedback_type=FeedbackType.NEGATIVE, rating=2)
        assert neg_feedback.is_positive() is False
    
    def test_feedback_to_dict(self):
        """Test feedback serialization."""
        feedback = HumanFeedback(
            decision_id="dec-1",
            feedback_type=FeedbackType.CORRECTIVE,
            content="Fix the bug",
            rating=3,
        )
        result = feedback.to_dict()
        assert result["decision_id"] == "dec-1"
        assert result["feedback_type"] == "corrective"
        assert result["rating"] == 3


class TestFeedbackCollector:
    """Test FeedbackCollector class."""
    
    def test_submit_feedback(self):
        """Test submitting feedback."""
        collector = FeedbackCollector()
        feedback = HumanFeedback(decision_id="dec-1", rating=4)
        feedback_id = collector.submit_feedback(feedback)
        
        assert feedback_id == feedback.feedback_id
        assert collector.get_feedback(feedback_id) is not None
    
    def test_get_decision_feedback(self):
        """Test getting feedback for decision."""
        collector = FeedbackCollector()
        fb1 = HumanFeedback(decision_id="dec-1", rating=5)
        fb2 = HumanFeedback(decision_id="dec-1", rating=4)
        fb3 = HumanFeedback(decision_id="dec-2", rating=3)
        
        collector.submit_feedback(fb1)
        collector.submit_feedback(fb2)
        collector.submit_feedback(fb3)
        
        dec1_feedback = collector.get_decision_feedback("dec-1")
        assert len(dec1_feedback) == 2
        
        dec2_feedback = collector.get_decision_feedback("dec-2")
        assert len(dec2_feedback) == 1
    
    def test_get_decision_quality_score(self):
        """Test quality score calculation."""
        collector = FeedbackCollector()
        fb1 = HumanFeedback(decision_id="dec-1", rating=5)
        fb2 = HumanFeedback(decision_id="dec-1", rating=5)
        
        collector.submit_feedback(fb1)
        collector.submit_feedback(fb2)
        
        score = collector.get_decision_quality_score("dec-1")
        assert 0.8 < score <= 1.0  # Should be close to 1.0
    
    def test_get_improvement_areas(self):
        """Test improvement area identification."""
        collector = FeedbackCollector()
        
        # Add low quality feedback
        for _ in range(3):
            fb = HumanFeedback(decision_id="poor-dec", rating=2, suggested_action="Improve this")
            collector.submit_feedback(fb)
        
        improvements = collector.get_improvement_areas(min_feedback_count=2)
        assert len(improvements) > 0
    
    def test_get_statistics(self):
        """Test statistics generation."""
        collector = FeedbackCollector()
        
        fb1 = HumanFeedback(decision_id="dec-1", feedback_type=FeedbackType.POSITIVE, rating=5)
        fb2 = HumanFeedback(decision_id="dec-1", feedback_type=FeedbackType.NEGATIVE, rating=2)
        fb3 = HumanFeedback(decision_id="dec-2", feedback_type=FeedbackType.CORRECTIVE, rating=3)
        
        collector.submit_feedback(fb1)
        collector.submit_feedback(fb2)
        collector.submit_feedback(fb3)
        
        stats = collector.get_statistics()
        assert stats["total_feedbacks"] == 3
        assert stats["unique_decisions"] == 2
        assert stats["positive_count"] == 1


class TestApprovalRequest:
    """Test ApprovalRequest class."""
    
    def test_create_request(self):
        """Test creating approval request."""
        request = ApprovalRequest(
            decision_id="dec-1",
            description="Approve policy change",
            required_approvers=2,
        )
        assert request.decision_id == "dec-1"
        assert request.required_approvers == 2
        assert request.status == ApprovalStatus.PENDING
    
    def test_add_approval(self):
        """Test adding approvals."""
        request = ApprovalRequest(
            decision_id="dec-1",
            required_approvers=2,
        )
        
        result1 = request.add_approval("approver1")
        assert result1 is False  # Not final
        assert request.current_approvals == 1
        
        result2 = request.add_approval("approver2")
        assert result2 is True  # Final approval
        assert request.is_approved() is True
    
    def test_reject_request(self):
        """Test rejecting a request."""
        request = ApprovalRequest(decision_id="dec-1")
        request.reject()
        assert request.status == ApprovalStatus.REJECTED
        assert request.is_approved() is False
    
    def test_request_expiration(self):
        """Test request expiration."""
        from datetime import timedelta
        
        from datetime import datetime, timezone

        request = ApprovalRequest(
            decision_id="dec-1",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        assert request.is_expired() is True


class TestApprovalWorkflow:
    """Test ApprovalWorkflow class."""
    
    def test_create_request(self):
        """Test creating approval request."""
        workflow = ApprovalWorkflow()
        request = workflow.create_request("dec-1", "Approve this")
        
        assert request.decision_id == "dec-1"
        assert workflow.get_request(request.request_id) is not None
    
    def test_approve_request(self):
        """Test approving a request."""
        workflow = ApprovalWorkflow()
        request = workflow.create_request("dec-1", "Approve", required_approvers=1)
        
        result = workflow.approve(request.request_id, "approver1")
        assert result is True
        assert request.is_approved() is True
    
    def test_reject_request(self):
        """Test rejecting a request."""
        workflow = ApprovalWorkflow()
        request = workflow.create_request("dec-1", "Approve")
        
        result = workflow.reject(request.request_id)
        assert result is True
        assert request.status == ApprovalStatus.REJECTED
    
    @pytest.mark.asyncio
    async def test_wait_for_approval(self):
        """Test waiting for approval."""
        workflow = ApprovalWorkflow()
        request = workflow.create_request("dec-1", "Approve", required_approvers=1)
        
        # Approve in background
        async def approve_later():
            await asyncio.sleep(0.1)
            workflow.approve(request.request_id, "approver1")
        
        task = asyncio.create_task(approve_later())
        result = await workflow.wait_for_approval(request.request_id)
        await task
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_wait_for_approval_timeout(self):
        """Test approval timeout."""
        workflow = ApprovalWorkflow(default_timeout_seconds=1)
        request = workflow.create_request("dec-1", "Approve")
        
        result = await workflow.wait_for_approval(request.request_id, timeout=0.1)
        assert result is False
        assert request.status == ApprovalStatus.EXPIRED
    
    def test_get_pending_requests(self):
        """Test getting pending requests."""
        workflow = ApprovalWorkflow()
        req1 = workflow.create_request("dec-1", "Approve")
        req2 = workflow.create_request("dec-2", "Approve")
        
        workflow.approve(req1.request_id, "approver1")
        
        pending = workflow.get_pending_requests()
        assert len(pending) == 1
        assert pending[0].request_id == req2.request_id
    
    def test_get_workflow_status(self):
        """Test workflow status."""
        workflow = ApprovalWorkflow()
        req1 = workflow.create_request("dec-1", "Approve")
        req2 = workflow.create_request("dec-2", "Approve")
        
        workflow.approve(req1.request_id, "approver1")
        workflow.reject(req2.request_id)
        
        status = workflow.get_workflow_status()
        assert status["total_requests"] == 2
        assert status["approved"] == 1
        assert status["rejected"] == 1


class TestHumanInTheLoopAgent:
    """Test HumanInTheLoopAgent class."""
    
    def test_create_agent(self):
        """Test creating HITL agent."""
        mock_agent = type('MockAgent', (), {})()
        workflow = ApprovalWorkflow()
        
        agent = HumanInTheLoopAgent(mock_agent, workflow)
        assert agent.base_agent is mock_agent
        assert agent.approval_workflow is workflow
    
    @pytest.mark.asyncio
    async def test_default_approval_policy(self):
        """Test default approval policy."""
        class MockAgent:
            async def make_decision(self, prompt, context=None):
                return {"id": "dec-1", "action": "execute"}
        
        mock_agent = MockAgent()
        workflow = ApprovalWorkflow()
        agent = HumanInTheLoopAgent(mock_agent, workflow)
        
        result = await agent.make_decision("Do something")
        assert result["action"] == "execute"
        assert "approval_status" not in result  # No approval needed
    
    @pytest.mark.asyncio
    async def test_approval_required_decision(self):
        """Test decision that requires approval."""
        class MockAgent:
            async def make_decision(self, prompt, context=None):
                return {"id": "dec-1", "risk_level": "high"}
        
        # Policy: approve high risk decisions
        def approval_policy(decision):
            return decision.get("risk_level") == "high"
        
        mock_agent = MockAgent()
        workflow = ApprovalWorkflow()
        agent = HumanInTheLoopAgent(mock_agent, workflow, approval_policy)
        
        # Make decision and immediately approve
        async def approve_later():
            await asyncio.sleep(0.05)
            pending = workflow.get_pending_requests()
            if pending:
                workflow.approve(pending[0].request_id, "approver")
        
        task = asyncio.create_task(approve_later())
        result = await agent.make_decision("Risky action")
        await task
        
        assert result["approval_status"] == "approved"
