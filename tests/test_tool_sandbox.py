"""Tests for tool sandbox behavior."""

import time

from agent_sdk.sandbox import LocalToolSandbox
from agent_sdk.exceptions import ToolError


def test_local_tool_sandbox_runs():
    sandbox = LocalToolSandbox(timeout_seconds=1.0)
    result = sandbox.run(lambda inputs: inputs["value"] + 1, {"value": 1})
    assert result == 2


def test_local_tool_sandbox_timeout():
    sandbox = LocalToolSandbox(timeout_seconds=0.01)
    def slow_tool(_inputs):
        time.sleep(0.1)
        return "ok"
    try:
        sandbox.run(slow_tool, {})
    except ToolError as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("Expected ToolError on timeout")
