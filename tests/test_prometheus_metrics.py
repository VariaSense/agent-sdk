"""Tests for Prometheus metrics endpoint."""

import os
import tempfile

from fastapi.testclient import TestClient

from agent_sdk.server.app import create_app


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


def test_prometheus_metrics_endpoint_enabled(monkeypatch):
    monkeypatch.setenv("AGENT_SDK_PROMETHEUS_ENABLED", "true")
    monkeypatch.setenv("AGENT_SDK_TRACING_ENABLED", "true")
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        assert app.state.observability is not None
        app.state.observability.record_metric("test_metric", 1.0, unit="ms")
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.text
        assert "agent_sdk_up" in body
        assert "agent_sdk_metric_last" in body
        assert "test_metric" in body


def test_prometheus_metrics_endpoint_disabled(monkeypatch):
    monkeypatch.delenv("AGENT_SDK_PROMETHEUS_ENABLED", raising=False)
    monkeypatch.setenv("AGENT_SDK_TRACING_ENABLED", "true")
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 404
