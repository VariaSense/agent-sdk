"""Human-in-the-loop agent wrapper."""

from typing import Any, Dict, Optional, Callable
import asyncio
from agent_sdk.human_in_the_loop.approval import ApprovalWorkflow


class HumanInTheLoopAgent:
    """Wraps an agent with human approval requirements.
    
    Allows certain decisions to require human approval before execution,
    enabling quality control and safety gates.
    """
    
    def __init__(
        self,
        base_agent: Any,
        approval_workflow: ApprovalWorkflow,
        approval_policy: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ):
        """Initialize HITL agent.
        
        Args:
            base_agent: Agent to wrap
            approval_workflow: ApprovalWorkflow instance
            approval_policy: Function to determine if decision needs approval
        """
        self.base_agent = base_agent
        self.approval_workflow = approval_workflow
        self.approval_policy = approval_policy or self._default_approval_policy
        self.decisions: Dict[str, Dict[str, Any]] = {}
    
    def _default_approval_policy(self, decision: Dict[str, Any]) -> bool:
        """Default approval policy - never require approval.
        
        Args:
            decision: Decision data
            
        Returns:
            True if approval needed
        """
        return False
    
    async def make_decision(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a decision, with optional human approval.
        
        Args:
            prompt: Decision prompt
            context: Additional context
            
        Returns:
            Decision result
        """
        # Get base decision
        decision = await self.base_agent.make_decision(prompt, context)
        
        # Check if approval needed
        if not self.approval_policy(decision):
            return decision
        
        # Request approval
        request = self.approval_workflow.create_request(
            decision_id=decision.get("id", "unknown"),
            description=f"Approval needed for: {prompt[:100]}",
            decision_data=decision,
        )
        
        # Wait for approval
        approved = await self.approval_workflow.wait_for_approval(request.request_id)
        
        if not approved:
            decision["status"] = "rejected"
            decision["approval_status"] = "rejected"
            return decision
        
        decision["approval_status"] = "approved"
        self.decisions[decision.get("id", request.request_id)] = decision
        
        return decision
    
    def get_decision_history(self) -> Dict[str, Dict[str, Any]]:
        """Get history of decisions."""
        return self.decisions.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_type": self.__class__.__name__,
            "total_decisions": len(self.decisions),
            "workflow_status": self.approval_workflow.get_workflow_status(),
        }
