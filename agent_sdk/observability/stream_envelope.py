"""
Event envelope schema and run/session metadata models.

This is the stable streaming contract for platform integrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import json
import uuid


class StreamChannel(str, Enum):
    """High-level stream category for event routing."""

    ASSISTANT = "assistant"
    TOOL = "tool"
    LIFECYCLE = "lifecycle"


class RunStatus(str, Enum):
    """Status for a run lifecycle."""

    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELED = "canceled"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


def new_session_id() -> str:
    return f"sess_{uuid.uuid4().hex}"


@dataclass(frozen=True)
class SessionMetadata:
    """Metadata for a session."""

    session_id: str
    org_id: str = "default"
    user_id: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunMetadata:
    """Metadata for a single run."""

    run_id: str
    session_id: str
    agent_id: str
    org_id: str = "default"
    status: RunStatus = RunStatus.ACCEPTED
    model: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamEnvelope:
    """Stable envelope for streaming events."""

    run_id: str
    session_id: str
    stream: StreamChannel
    event: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=_now_iso)
    seq: Optional[int] = None
    status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "stream": self.stream.value,
            "event": self.event,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
        if self.seq is not None:
            data["seq"] = self.seq
        if self.status is not None:
            data["status"] = self.status
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    def to_sse(self) -> str:
        return f"data: {self.to_json()}\n\n"


def is_valid_run_transition(current: RunStatus, new: RunStatus) -> bool:
    """Validate run status transitions."""
    if current == new:
        return True
    allowed = {
        RunStatus.ACCEPTED: {
            RunStatus.RUNNING,
            RunStatus.COMPLETED,
            RunStatus.ERROR,
            RunStatus.CANCELED,
            RunStatus.TIMEOUT,
        },
        RunStatus.RUNNING: {
            RunStatus.COMPLETED,
            RunStatus.ERROR,
            RunStatus.CANCELED,
            RunStatus.TIMEOUT,
        },
    }
    return new in allowed.get(current, set())
