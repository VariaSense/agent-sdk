"""Interface contracts for external dependencies."""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Dict, Any, List, Optional, Iterable

from agent_sdk.config.model_config import ModelConfig
from agent_sdk.llm.base import LLMResponse
from agent_sdk.observability.stream_envelope import RunMetadata, SessionMetadata, StreamEnvelope
from agent_sdk.identity.providers import IdentityClaims


@runtime_checkable
class LLMClientContract(Protocol):
    def generate(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        ...

    async def generate_async(
        self, messages: List[Dict[str, str]], model_config: ModelConfig
    ) -> LLMResponse:
        ...


@runtime_checkable
class ToolCallableContract(Protocol):
    def __call__(self, args: Dict[str, Any]) -> Any:
        ...

    async def call_async(self, args: Dict[str, Any]) -> Any:
        ...


@runtime_checkable
class StorageContract(Protocol):
    def create_session(self, session: SessionMetadata) -> None:
        ...

    def update_session(self, session: SessionMetadata) -> None:
        ...

    def get_session(self, session_id: str) -> Optional[SessionMetadata]:
        ...

    def list_sessions(self, limit: int = 100) -> List[SessionMetadata]:
        ...

    def create_run(self, run: RunMetadata) -> None:
        ...

    def update_run(self, run: RunMetadata) -> None:
        ...

    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        ...

    def list_runs(self, org_id: Optional[str] = None, limit: int = 1000) -> List[RunMetadata]:
        ...

    def append_event(self, event: StreamEnvelope) -> None:
        ...

    def list_events(self, run_id: str, limit: int = 1000) -> List[StreamEnvelope]:
        ...

    def list_events_from(
        self,
        run_id: str,
        from_seq: Optional[int] = None,
        limit: int = 1000,
    ) -> List[StreamEnvelope]:
        ...

    def delete_events(self, run_id: str, before_seq: Optional[int] = None) -> int:
        ...

    def recover_in_flight_runs(self) -> int:
        ...

    def delete_run(self, run_id: str) -> int:
        ...

    def delete_session(self, session_id: str) -> int:
        ...


@runtime_checkable
class IdentityProviderContract(Protocol):
    def validate(self, token: str) -> IdentityClaims:
        ...


@runtime_checkable
class SecretsProviderContract(Protocol):
    def get(self, key: str) -> Optional[str]:
        ...


@runtime_checkable
class WebhookSenderContract(Protocol):
    def send(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> None:
        ...


@runtime_checkable
class PolicyRegistryContract(Protocol):
    def list_policies(self) -> Iterable[Dict[str, Any]]:
        ...

    def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        ...
