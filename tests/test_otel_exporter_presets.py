"""Tests for OpenTelemetry exporter presets."""

import os

from agent_sdk.observability.otel import ObservabilityManager


def test_otel_exporter_stdout(monkeypatch):
    monkeypatch.setenv("AGENT_SDK_OTEL_EXPORTER", "stdout")
    obs = ObservabilityManager(service_name="agent-sdk-test")
    assert obs.tracer._otel_tracer is not None
    with obs.trace_agent_execution("agent", "goal") as span:
        span.add_attribute("test", "value")


def test_otel_exporter_disabled(monkeypatch):
    monkeypatch.delenv("AGENT_SDK_OTEL_EXPORTER", raising=False)
    obs = ObservabilityManager(service_name="agent-sdk-test")
    assert obs.tracer._otel_tracer is None
