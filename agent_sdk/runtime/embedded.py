"""Adapter that exposes a simple runtime contract on top of PlannerExecutorRuntime."""

from __future__ import annotations

from agent_sdk.config.model_config import ModelConfig
from agent_sdk.contracts.runtime import (
    AgentDefinition,
    ExecutionMetadata,
    RunEvent,
    RunRequest,
    RunResult,
)
from agent_sdk.core.context import AgentContext
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.execution.executor import ExecutorAgent
from agent_sdk.llm.base import LLMClient
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.ports import AgentRuntimePort
from agent_sdk.planning.planner import PlannerAgent


class EmbeddedAgentRunner(AgentRuntimePort):
    """Reusable runtime entrypoint for applications embedding agent-sdk."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or MockLLMClient()

    def _build_runtime(self, agent: AgentDefinition) -> PlannerExecutorRuntime:
        model = ModelConfig(name=agent.model, provider="embedded", model_id=agent.model)
        planner_context = AgentContext(model_config=model)
        executor_context = AgentContext(model_config=model)
        planner = PlannerAgent("planner", planner_context, self.llm_client)
        executor = ExecutorAgent("executor", executor_context, self.llm_client)
        return PlannerExecutorRuntime(planner, executor)

    def run(self, request: RunRequest) -> RunResult:
        runtime = self._build_runtime(request.agent)
        messages = runtime.run(
            request.prompt,
            session_id=request.metadata.session_id,
            run_id=request.metadata.run_id,
            org_id=request.metadata.org_id,
        )
        response = messages[-1].content if messages else ""
        events = [
            RunEvent(
                stream="lifecycle",
                event="started",
                payload={"agent": request.agent.name, "correlation_id": request.metadata.correlation_id},
            ),
            RunEvent(
                stream="assistant",
                event="message",
                payload={"response": response, "correlation_id": request.metadata.correlation_id},
            ),
            RunEvent(
                stream="lifecycle",
                event="completed",
                payload={"agent": request.agent.name, "correlation_id": request.metadata.correlation_id},
            ),
        ]
        return RunResult(
            status="completed",
            response=response,
            events=events,
            tools_used=request.agent.tools[:],
            metadata=ExecutionMetadata.model_validate(request.metadata.model_dump()),
            debug={
                "message_count": len(messages),
                "runner": "agent_sdk.runtime.EmbeddedAgentRunner",
            },
        )
