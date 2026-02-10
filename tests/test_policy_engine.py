"""Tests for governance policy engine enforcement."""

from agent_sdk.core.context import AgentContext
from agent_sdk.execution.executor import ExecutorAgent
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.core.tools import Tool
from agent_sdk.planning.plan_schema import PlanStep
from agent_sdk.policy.engine import PolicyEngine
from agent_sdk.server.multi_tenant import MultiTenantStore


def test_policy_engine_denies_tool():
    store = MultiTenantStore()
    bundle = store.create_policy_bundle(
        "deny-tools",
        content={"tools": {"deny": ["test.tool"]}},
    )
    store.assign_policy_bundle("default", bundle.bundle_id, bundle.version)
    engine = PolicyEngine(store)

    context = AgentContext(tools={"test.tool": Tool(name="test.tool", description="t", func=lambda _: "ok")})
    context.org_id = "default"
    context.config["policy_engine"] = engine

    executor = ExecutorAgent("executor", context, MockLLMClient())
    step = PlanStep(id="1", description="blocked", tool="test.tool", inputs={})
    result = executor._run_tool(step)
    assert result.success is False
    assert "Policy denied" in (result.error or "")


def test_policy_engine_denies_egress():
    store = MultiTenantStore()
    bundle = store.create_policy_bundle(
        "deny-egress",
        content={"egress": {"deny_domains": ["example.com"]}},
    )
    store.assign_policy_bundle("default", bundle.bundle_id, bundle.version)
    engine = PolicyEngine(store)

    context = AgentContext(
        tools={"http.fetch": Tool(name="http.fetch", description="t", func=lambda _: "ok")}
    )
    context.org_id = "default"
    context.config["policy_engine"] = engine

    executor = ExecutorAgent("executor", context, MockLLMClient())
    step = PlanStep(id="1", description="blocked", tool="http.fetch", inputs={"url": "https://example.com"})
    result = executor._run_tool(step)
    assert result.success is False
    assert "Policy denied egress" in (result.error or "")
