"""Tests for identity group mapping in auth validation."""

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


def test_group_mapping_enriches_identity(monkeypatch):
    monkeypatch.setenv("AGENT_SDK_GROUP_ROLE_MAP", '{"admins": "admin"}')
    monkeypatch.setenv("AGENT_SDK_GROUP_SCOPE_MAP", '{"admins": ["runs:read", "runs:write"]}')
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        client = TestClient(app)
        response = client.post(
            "/auth/validate",
            json={"token": "mock:{\"sub\": \"user1\", \"groups\": [\"admins\"]}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload.get("role") == "admin"
        assert "runs:read" in payload.get("scopes", [])
