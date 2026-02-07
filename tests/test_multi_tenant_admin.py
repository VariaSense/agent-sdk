"""Tests for admin endpoints for multi-tenant readiness."""

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
    monkeypatch.setenv("API_KEY", "test-key")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_admin_orgs_and_keys(client):
    orgs = client.get("/admin/orgs", headers={"X-API-Key": "test-key"})
    assert orgs.status_code == 200
    org_list = orgs.json()
    assert any(org["org_id"] == "default" for org in org_list)

    created = client.post(
        "/admin/api-keys",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "label": "test"},
    )
    assert created.status_code == 200
    data = created.json()
    assert data["org_id"] == "default"
    assert data["key"].startswith("sk_")

    keys = client.get("/admin/api-keys", headers={"X-API-Key": "test-key"})
    assert keys.status_code == 200
    assert len(keys.json()) >= 1


def test_admin_usage(client):
    usage = client.get("/admin/usage", headers={"X-API-Key": "test-key"})
    assert usage.status_code == 200
    data = usage.json()
    assert any(item["org_id"] == "default" for item in data)
