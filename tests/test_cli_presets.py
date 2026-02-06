"""
Tests for CLI wiring without invoking Typer runner (compat issues on py3.14).
"""

from agent_sdk.cli.main import app
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.presets.runtime import build_runtime_from_preset


def test_server_alias_present():
    group_names = [g.name for g in app.registered_groups]
    assert "server" in group_names


def test_build_runtime_from_preset():
    runtime = build_runtime_from_preset("assistant_basic", MockLLMClient())
    assert runtime.planner.context.tools
