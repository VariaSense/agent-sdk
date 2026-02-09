"""Tests for tracing integration."""

import os
import tempfile
import asyncio

from agent_sdk.config.loader import load_config
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.observability.otel import ObservabilityManager


def _write_config(tmpdir: str) -> str:
    config_path = os.path.join(tmpdir, "config.yaml")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(
            """
models:
  mock:
    name: mock
    provider: mock
    model_id: mock
agents:
  planner:
    model: mock
  executor:
    model: mock
rate_limits: []
"""
        )
    return config_path


def test_tracing_spans_created():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            planner, executor = load_config(_write_config(tmpdir), MockLLMClient())
            obs = ObservabilityManager(service_name="agent-sdk-test")
            planner.context.config["observability"] = obs
            executor.context.config["observability"] = obs
            runtime = PlannerExecutorRuntime(planner, executor)
            await runtime.run_async("test tracing")
            return obs

    obs = asyncio.run(_run())
    span_names = [span.name for span in obs.tracer.spans.values()]
    assert any("agent_execute" in name for name in span_names)
    assert any("model_call" in name for name in span_names)
