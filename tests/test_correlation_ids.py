"""Tests for correlation IDs in responses."""

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


def test_correlation_headers_present():
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.headers.get("X-Request-Id")
        assert response.headers.get("X-Trace-Id")
