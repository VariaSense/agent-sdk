"""Tests for RBAC and scope enforcement."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app
from agent_sdk.security import get_api_key_manager


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
        monkeypatch.setenv("AGENT_SDK_DB_PATH", os.path.join(tmpdir, "agent_sdk.db"))
        app = create_app(config_path=_write_config(tmpdir))
        manager = get_api_key_manager()
        manager.add_key("dev-key", role="developer")
        manager.add_key("viewer-key", role="viewer")
        yield TestClient(app)


def test_admin_endpoint_requires_admin_scope(client):
    response = client.get("/admin/orgs", headers={"X-API-Key": "dev-key"})
    assert response.status_code == 403

    response = client.get("/admin/orgs", headers={"X-API-Key": "admin-key"})
    assert response.status_code == 200


def test_viewer_cannot_run_task(client):
    response = client.post(
        "/run",
        headers={"X-API-Key": "viewer-key"},
        json={"task": "hello"},
    )
    assert response.status_code == 403

    response = client.post(
        "/run",
        headers={"X-API-Key": "dev-key"},
        json={"task": "hello"},
    )
    assert response.status_code == 200
