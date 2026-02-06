"""Deterministic mocks for LLMs and tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agent_sdk.config.model_config import ModelConfig
from agent_sdk.core.tools import Tool
from agent_sdk.llm.base import LLMClient, LLMResponse


class DeterministicLLMClient(LLMClient):
    """LLM mock that returns deterministic, scripted responses."""

    def __init__(self, responses: Optional[List[str]] = None):
        self._responses = list(responses or [])
        self._index = 0
        self.calls: List[List[Dict[str, str]]] = []

    def _next_text(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> str:
        if self._responses:
            if self._index < len(self._responses):
                text = self._responses[self._index]
                self._index += 1
                return text
            return self._responses[-1]
        last = messages[-1]["content"]
        return f"[{model_config.name}] {last}"

    def generate(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        self.calls.append(messages)
        text = self._next_text(messages, model_config)
        prompt_tokens = sum(len(m["content"].split()) for m in messages)
        completion_tokens = len(text.split())
        total_tokens = prompt_tokens + completion_tokens
        return LLMResponse(text, prompt_tokens, completion_tokens, total_tokens)

    async def generate_async(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        return self.generate(messages, model_config)

    def reset(self) -> None:
        self._index = 0
        self.calls = []


@dataclass
class ToolMock:
    """Tool mock with deterministic outputs."""

    outputs: List[Any]
    name: str = "mock_tool"
    description: str = "Mock tool for tests"

    def __post_init__(self) -> None:
        self._index = 0
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, args: Dict[str, Any]) -> Any:
        self.calls.append(args)
        if not self.outputs:
            return None
        if self._index < len(self.outputs):
            value = self.outputs[self._index]
            self._index += 1
            return value
        return self.outputs[-1]

    async def call_async(self, args: Dict[str, Any]) -> Any:
        return self(args)

    def as_tool(self) -> Tool:
        return Tool(name=self.name, description=self.description, func=self)
