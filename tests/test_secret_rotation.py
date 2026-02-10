"""Tests for secret rotation policies."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
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


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_KEY", "admin-key")
    monkeypatch.setenv("API_KEY_ROLE", "admin")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_secret_rotation_endpoints(client):
    set_resp = client.post(
        "/admin/secrets/rotation",
        headers={"X-API-Key": "admin-key"},
        json={"org_id": "default", "secret_id": "openai", "rotation_days": 30},
    )
    assert set_resp.status_code == 200

    list_resp = client.get(
        "/admin/secrets/rotation",
        headers={"X-API-Key": "admin-key"},
    )
    assert list_resp.status_code == 200
    assert any(item["secret_id"] == "openai" for item in list_resp.json())

    health = client.get(
        "/admin/secrets/health",
        headers={"X-API-Key": "admin-key"},
    )
    assert health.status_code == 200
