"""Integration tests for planner-executor runtime."""

import asyncio

from agent_sdk.core.context import AgentContext
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.execution.executor import ExecutorAgent
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.planning.planner import PlannerAgent
from agent_sdk.config.model_config import ModelConfig


def _build_runtime():
    model = ModelConfig(name="mock", provider="mock", model_id="mock")
    llm = MockLLMClient()
    planner_context = AgentContext(model_config=model)
    executor_context = AgentContext(model_config=model)
    planner = PlannerAgent("planner", planner_context, llm)
    executor = ExecutorAgent("executor", executor_context, llm)
    return PlannerExecutorRuntime(planner, executor)


def test_runtime_run_async_end_to_end():
    runtime = _build_runtime()
    messages = asyncio.run(runtime.run_async("Write a short greeting"))

    assert len(messages) == 2
    plan_msg, exec_msg = messages
    assert plan_msg.metadata.get("type") == "plan"
    assert exec_msg.metadata.get("type") == "execution_step"
    assert plan_msg.metadata.get("run_id")
    assert exec_msg.metadata.get("session_id")


def test_context_memory_limits_enforced():
    context = AgentContext()
    for i in range(1005):
        context.add_short_term_message({"role": "user", "content": f"msg {i}"})
    assert len(context.short_term) <= context.max_short_term
