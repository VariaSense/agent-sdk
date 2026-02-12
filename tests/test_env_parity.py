"""Tests for environment parity checks."""

from agent_sdk.config.parity import check_env_parity


def test_env_parity_examples():
    missing = check_env_parity("deploy/env")
    assert missing == {}
