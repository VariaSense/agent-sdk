from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class PolicyApprovalStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PolicyBundle:
    bundle_id: str
    version: int
    content: Dict[str, Any]
    description: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class PolicyAssignment:
    org_id: str
    bundle_id: str
    version: int
    overrides: Dict[str, Any] = field(default_factory=dict)
    assigned_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class PolicyApproval:
    bundle_id: str
    version: int
    status: str = PolicyApprovalStatus.PENDING
    submitted_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    submitted_at: str = field(default_factory=_now_iso)
    reviewed_at: Optional[str] = None
    notes: Optional[str] = None
    org_id: Optional[str] = None
