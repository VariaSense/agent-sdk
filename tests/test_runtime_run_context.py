"""
Tests for run/session context propagation in runtime.
"""

from agent_sdk.core.context import AgentContext
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.planning.planner import PlannerAgent
from agent_sdk.execution.executor import ExecutorAgent
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.config.model_config import ModelConfig


def _make_runtime():
    model_config = ModelConfig(name="mock", provider="mock", model_id="mock")
    llm = MockLLMClient()
    planner_context = AgentContext(model_config=model_config)
    executor_context = AgentContext(model_config=model_config)
    planner = PlannerAgent("planner", planner_context, llm)
    executor = ExecutorAgent("executor", executor_context, llm)
    return PlannerExecutorRuntime(planner, executor)


def test_run_context_propagation_with_explicit_ids():
    runtime = _make_runtime()
    messages = runtime.run("hello", session_id="sess_test", run_id="run_test")

    assert runtime.planner.context.session_id == "sess_test"
    assert runtime.executor.context.session_id == "sess_test"
    assert runtime.planner.context.run_id == "run_test"
    assert runtime.executor.context.run_id == "run_test"

    plan_msg, exec_msg = messages
    assert plan_msg.metadata["session_id"] == "sess_test"
    assert plan_msg.metadata["run_id"] == "run_test"
    assert exec_msg.metadata["session_id"] == "sess_test"
    assert exec_msg.metadata["run_id"] == "run_test"


def test_run_context_generates_ids_and_preserves_session():
    runtime = _make_runtime()
    first_messages = runtime.run("first run")
    first_plan, first_exec = first_messages

    session_id = runtime.planner.context.session_id
    run_id = runtime.planner.context.run_id

    assert session_id is not None
    assert run_id is not None
    assert first_plan.metadata["session_id"] == session_id
    assert first_exec.metadata["run_id"] == run_id

    second_messages = runtime.run("second run")
    second_plan, second_exec = second_messages

    assert runtime.planner.context.session_id == session_id
    assert runtime.executor.context.session_id == session_id
    assert runtime.planner.context.run_id != run_id
    assert runtime.executor.context.run_id != run_id
    assert second_plan.metadata["session_id"] == session_id
    assert second_exec.metadata["session_id"] == session_id
