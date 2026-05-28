"""Contracts for wrapping third-party agent runtimes."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from agent_sdk.contracts.runtime import CONTRACT_VERSION


class ExternalAgentCommand(BaseModel):
    """Command contract for a local third-party agent process."""

    contract_version: Literal["v1"] = CONTRACT_VERSION
    provider: str = Field(default="generic", min_length=1, max_length=100)
    executable: str = Field(..., min_length=1, max_length=500)
    args: list[str] = Field(default_factory=list)
    cwd: Optional[str] = None
    env: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=1800, ge=1, le=86400)
    prompt_mode: Literal["stdin", "argument"] = "stdin"
    output_format: Literal["text", "jsonl"] = "text"
    strip_ansi: bool = True
