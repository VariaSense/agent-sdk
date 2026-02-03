"""Approval workflow management."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable, List
from datetime import datetime
from enum import Enum
import uuid
import asyncio


class ApprovalStatus(Enum):
    """Status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """Request for human approval.
    
    Attributes:
        request_id: Unique request identifier
        decision_id: ID of decision requiring approval
        description: What needs approval
        required_approvers: Number of approvals needed
        current_approvals: Current approval count
        status: Current status
        created_at: Request creation time
        expires_at: When request expires
        decision_data: Full decision data for review
    """
    
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    description: str = ""
    required_approvers: int = 1
    current_approvals: int = 0
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    decision_data: Dict[str, Any] = field(default_factory=dict)
    approvers: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        """Check if request is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_approved(self) -> bool:
        """Check if approved."""
        return (
            self.status == ApprovalStatus.APPROVED or
            self.current_approvals >= self.required_approvers
        )
    
    def add_approval(self, approver: str) -> bool:
        """Record an approval.
        
        Args:
            approver: Approver identifier
            
        Returns:
            True if this was the final approval needed
        """
        if approver not in self.approvers:
            self.approvers.append(approver)
        
        self.current_approvals = len(self.approvers)
        
        if self.is_approved():
            self.status = ApprovalStatus.APPROVED
            return True
        
        return False
    
    def reject(self) -> None:
        """Reject the request."""
        self.status = ApprovalStatus.REJECTED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "decision_id": self.decision_id,
            "description": self.description,
            "required_approvers": self.required_approvers,
            "current_approvals": self.current_approvals,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired(),
            "approvers": self.approvers,
        }


class ApprovalWorkflow:
    """Manages approval workflows.
    
    Coordinates approval requests, tracks approvals,
    and enforces approval policies.
    """
    
    def __init__(self, default_timeout_seconds: int = 3600):
        """Initialize workflow.
        
        Args:
            default_timeout_seconds: Default approval timeout
        """
        self.default_timeout = default_timeout_seconds
        self.requests: Dict[str, ApprovalRequest] = {}
        self._waiters: Dict[str, List[asyncio.Future]] = {}
    
    def create_request(
        self,
        decision_id: str,
        description: str,
        required_approvers: int = 1,
        decision_data: Optional[Dict[str, Any]] = None,
    ) -> ApprovalRequest:
        """Create an approval request.
        
        Args:
            decision_id: ID of decision
            description: Description of what needs approval
            required_approvers: Number of approvals needed
            decision_data: Data to include with request
            
        Returns:
            ApprovalRequest instance
        """
        from datetime import timedelta
        
        request = ApprovalRequest(
            decision_id=decision_id,
            description=description,
            required_approvers=required_approvers,
            decision_data=decision_data or {},
            expires_at=datetime.utcnow() + timedelta(seconds=self.default_timeout),
        )
        
        self.requests[request.request_id] = request
        self._waiters[request.request_id] = []
        
        return request
    
    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by ID."""
        return self.requests.get(request_id)
    
    def approve(self, request_id: str, approver: str) -> bool:
        """Approve a request.
        
        Args:
            request_id: Request ID
            approver: Approver identifier
            
        Returns:
            True if this was the final approval
        """
        request = self.requests.get(request_id)
        if not request:
            return False
        
        is_final = request.add_approval(approver)
        
        # Notify waiters
        if request_id in self._waiters:
            for waiter in self._waiters[request_id]:
                if not waiter.done():
                    waiter.set_result(True)
        
        return is_final
    
    def reject(self, request_id: str) -> bool:
        """Reject a request.
        
        Args:
            request_id: Request ID
            
        Returns:
            True if rejected
        """
        request = self.requests.get(request_id)
        if not request:
            return False
        
        request.reject()
        
        # Notify waiters
        if request_id in self._waiters:
            for waiter in self._waiters[request_id]:
                if not waiter.done():
                    waiter.set_result(False)
        
        return True
    
    async def wait_for_approval(self, request_id: str, timeout: Optional[float] = None) -> bool:
        """Wait for approval of a request.
        
        Args:
            request_id: Request ID
            timeout: Timeout in seconds
            
        Returns:
            True if approved, False if rejected
        """
        request = self.requests.get(request_id)
        if not request:
            return False
        
        # Already approved
        if request.is_approved():
            return True
        
        # Already rejected
        if request.status == ApprovalStatus.REJECTED:
            return False
        
        # Already expired
        if request.is_expired():
            request.status = ApprovalStatus.EXPIRED
            return False
        
        # Wait for approval
        future: asyncio.Future = asyncio.Future()
        if request_id not in self._waiters:
            self._waiters[request_id] = []
        self._waiters[request_id].append(future)
        
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            request.status = ApprovalStatus.EXPIRED
            return False
    
    def get_pending_requests(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        return [
            r for r in self.requests.values()
            if r.status == ApprovalStatus.PENDING and not r.is_expired()
        ]
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get workflow status."""
        pending = self.get_pending_requests()
        approved = [r for r in self.requests.values() if r.status == ApprovalStatus.APPROVED]
        rejected = [r for r in self.requests.values() if r.status == ApprovalStatus.REJECTED]
        
        return {
            "total_requests": len(self.requests),
            "pending": len(pending),
            "approved": len(approved),
            "rejected": len(rejected),
            "pending_requests": [r.request_id for r in pending],
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        status = self.get_workflow_status()
        return {
            "default_timeout": self.default_timeout,
            **status,
        }
