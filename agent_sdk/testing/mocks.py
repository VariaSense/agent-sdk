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


class InMemoryStorage:
    """Simple in-memory storage backend for contract tests."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Any] = {}
        self._runs: Dict[str, Any] = {}
        self._events: Dict[str, List[Any]] = {}

    def create_session(self, session: Any) -> None:
        self._sessions[session.session_id] = session

    def update_session(self, session: Any) -> None:
        self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> Optional[Any]:
        return self._sessions.get(session_id)

    def list_sessions(self, limit: int = 100) -> List[Any]:
        return list(self._sessions.values())[:limit]

    def create_run(self, run: Any) -> None:
        self._runs[run.run_id] = run

    def update_run(self, run: Any) -> None:
        self._runs[run.run_id] = run

    def get_run(self, run_id: str) -> Optional[Any]:
        return self._runs.get(run_id)

    def list_runs(self, org_id: Optional[str] = None, limit: int = 1000) -> List[Any]:
        runs = list(self._runs.values())
        if org_id is not None:
            runs = [run for run in runs if getattr(run, "org_id", None) == org_id]
        return runs[:limit]

    def append_event(self, event: Any) -> None:
        self._events.setdefault(event.run_id, []).append(event)

    def list_events(self, run_id: str, limit: int = 1000) -> List[Any]:
        return list(self._events.get(run_id, []))[:limit]

    def list_events_from(
        self,
        run_id: str,
        from_seq: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Any]:
        events = list(self._events.get(run_id, []))
        if from_seq is not None:
            events = [event for event in events if event.seq is None or event.seq >= from_seq]
        return events[:limit]

    def delete_events(self, run_id: str, before_seq: Optional[int] = None) -> int:
        events = list(self._events.get(run_id, []))
        if before_seq is None:
            deleted = len(events)
            self._events[run_id] = []
            return deleted
        remaining = [event for event in events if event.seq is not None and event.seq >= before_seq]
        deleted = len(events) - len(remaining)
        self._events[run_id] = remaining
        return deleted

    def recover_in_flight_runs(self) -> int:
        return 0

    def delete_run(self, run_id: str) -> int:
        removed = 1 if run_id in self._runs else 0
        self._runs.pop(run_id, None)
        self._events.pop(run_id, None)
        return removed

    def delete_session(self, session_id: str) -> int:
        removed = 1 if session_id in self._sessions else 0
        self._sessions.pop(session_id, None)
        runs_to_delete = [run_id for run_id, run in self._runs.items() if run.session_id == session_id]
        for run_id in runs_to_delete:
            self.delete_run(run_id)
        return removed


class DummyWebhookSender:
    """Webhook sender that records payloads for assertions."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def send(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> None:
        self.calls.append({"payload": payload, "headers": headers or {}})
