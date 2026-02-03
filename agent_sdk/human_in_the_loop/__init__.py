"""Human-in-the-loop module for approval workflows and feedback collection.

This module provides tools for integrating human feedback into agent decisions,
implementing approval workflows, and active learning feedback loops.

Classes:
    HumanFeedback: Container for human feedback
    ApprovalRequest: Request for human approval
    ApprovalWorkflow: Manages approval processes
    FeedbackCollector: Collects user feedback
    HumanInTheLoopAgent: Wraps agent with approval requirements

Usage:
    from agent_sdk.human_in_the_loop import ApprovalWorkflow
    
    workflow = ApprovalWorkflow()
    request = workflow.create_request(decision)
    approval = await workflow.wait_for_approval(request_id)
"""

from agent_sdk.human_in_the_loop.feedback import (
    FeedbackType,
    HumanFeedback,
    FeedbackCollector,
)
from agent_sdk.human_in_the_loop.approval import (
    ApprovalStatus,
    ApprovalRequest,
    ApprovalWorkflow,
)
from agent_sdk.human_in_the_loop.agent import (
    HumanInTheLoopAgent,
)

__all__ = [
    "FeedbackType",
    "HumanFeedback",
    "FeedbackCollector",
    "ApprovalStatus",
    "ApprovalRequest",
    "ApprovalWorkflow",
    "HumanInTheLoopAgent",
]
