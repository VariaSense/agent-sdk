"""Tests for reliability policies and replay mode."""

import pytest

from agent_sdk.reliability.policy import ReliabilityManager, RetryPolicy, CircuitBreakerPolicy, ReplayStore
from agent_sdk.execution.executor import ExecutorAgent
from agent_sdk.core.context import AgentContext
from agent_sdk.core.tools import Tool
from agent_sdk.planning.plan_schema import PlanStep
from agent_sdk.llm.mock import MockLLMClient


def test_reliability_retry_and_circuit_breaker():
    attempts = {"count": 0}

    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("fail")
        return "ok"

    manager = ReliabilityManager(
        retry_policy=RetryPolicy(max_retries=2, base_delay=0.01, max_delay=0.02),
        breaker_policy=CircuitBreakerPolicy(failure_threshold=2, reset_timeout_seconds=60),
    )

    assert manager.execute("tool", flaky) == "ok"

    def always_fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        manager.execute("tool", always_fail)
    with pytest.raises(RuntimeError):
        manager.execute("tool", always_fail)
    with pytest.raises(RuntimeError):
        manager.execute("tool", always_fail)


def test_replay_store_short_circuits_tool_call():
    called = {"count": 0}

    def tool_fn(_):
        called["count"] += 1
        return "live"

    context = AgentContext(tools={"demo": Tool(name="demo", description="d", func=tool_fn)})
    store = ReplayStore({"step-1": "cached"})
    context.config["replay_store"] = store
    context.config["replay_mode"] = True
    executor = ExecutorAgent("executor", context, MockLLMClient())

    result = executor._run_tool(PlanStep(id="step-1", description="test", tool="demo", inputs={}))
    assert result.success is True
    assert result.output == "cached"
    assert called["count"] == 0
