"""Tests for API versioning middleware."""

import os
import tempfile

from fastapi.testclient import TestClient

from agent_sdk.server.app import create_app
import agent_sdk.security as security


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


def test_v1_health_route():
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        client = TestClient(app)
        response = client.get("/v1/health")
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"


def test_deprecation_header_on_unversioned_admin(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        client = TestClient(app)
        response = client.get("/admin/usage", headers={"X-API-Key": "test-key"})
        assert response.status_code == 200
        assert response.headers.get("X-API-Deprecated") is not None
