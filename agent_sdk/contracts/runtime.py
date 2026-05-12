"""Stable runtime contracts consumed by external applications."""

from __future__ import annotations

from typing import Any, Literal, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


CONTRACT_VERSION = "v1"


class AgentDefinition(BaseModel):
    contract_version: Literal["v1"] = CONTRACT_VERSION
    name: str = Field(..., min_length=1, max_length=200)
    model: str = Field(default="gpt-4o-mini", min_length=1, max_length=200)
    purpose: str = Field(default="", max_length=4000)
    tools: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    memory_enabled: bool = False


class ExecutionMetadata(BaseModel):
    contract_version: Literal["v1"] = CONTRACT_VERSION
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    org_id: Optional[str] = None
    correlation_id: Optional[str] = None


class RunRequest(BaseModel):
    contract_version: Literal["v1"] = CONTRACT_VERSION
    agent: AgentDefinition
    prompt: str = Field(..., min_length=1, max_length=20000)
    metadata: ExecutionMetadata = Field(default_factory=ExecutionMetadata)


class RunEvent(BaseModel):
    contract_version: Literal["v1"] = CONTRACT_VERSION
    stream: str
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    contract_version: Literal["v1"] = CONTRACT_VERSION
    status: str
    response: str
    events: list[RunEvent] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    metadata: ExecutionMetadata = Field(default_factory=ExecutionMetadata)
    debug: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class AgentRuntimeContract(Protocol):
    def run(self, request: RunRequest) -> RunResult:
        """Execute a run request and return a stable result payload."""
