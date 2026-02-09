"""Tests for tenant model policy resolution."""

from agent_sdk.server.multi_tenant import MultiTenantStore


def test_model_policy_resolution():
    store = MultiTenantStore()
    store.set_model_catalog(["gpt-4", "gpt-3.5"])
    store.set_model_policy("default", allowed_models=["gpt-3.5"], fallback_models=["gpt-3.5"])

    assert store.resolve_model("default", "gpt-3.5") == "gpt-3.5"
    assert store.resolve_model("default", "gpt-4") == "gpt-3.5"
