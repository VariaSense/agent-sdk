"""
Storage interfaces for runs, sessions, and streaming events.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from agent_sdk.observability.stream_envelope import RunMetadata, SessionMetadata, StreamEnvelope


class StorageBackend(ABC):
    """Abstract storage backend for platform data."""

    @abstractmethod
    def create_session(self, session: SessionMetadata) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_session(self, session: SessionMetadata) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[SessionMetadata]:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(self, limit: int = 100) -> List[SessionMetadata]:
        raise NotImplementedError

    @abstractmethod
    def create_run(self, run: RunMetadata) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_run(self, run: RunMetadata) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        raise NotImplementedError

    @abstractmethod
    def append_event(self, event: StreamEnvelope) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_events(self, run_id: str, limit: int = 1000) -> List[StreamEnvelope]:
        raise NotImplementedError

    @abstractmethod
    def list_events_from(
        self,
        run_id: str,
        from_seq: Optional[int] = None,
        limit: int = 1000,
    ) -> List[StreamEnvelope]:
        raise NotImplementedError

    @abstractmethod
    def delete_events(self, run_id: str, before_seq: Optional[int] = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def recover_in_flight_runs(self) -> int:
        """Mark in-flight runs as recovered after a restart."""
        raise NotImplementedError
