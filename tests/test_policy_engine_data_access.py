"""Tests for policy engine data access guardrails."""

from agent_sdk.policy.engine import PolicyEngine
from agent_sdk.server.multi_tenant import MultiTenantStore


def test_data_access_guardrails():
    store = MultiTenantStore()
    store.create_policy_bundle(
        "data-policy",
        content={"data_access": {"allow_classifications": ["public"], "allow_actions": ["read"]}},
    )
    store.assign_policy_bundle("default", "data-policy", 1)
    engine = PolicyEngine(store)
    allowed = engine.evaluate_data_access("default", "public", "read")
    denied = engine.evaluate_data_access("default", "restricted", "read")
    assert allowed.allowed is True
    assert denied.allowed is False
