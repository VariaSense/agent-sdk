"""Tests for identity validation and SCIM endpoints."""

import json
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
    monkeypatch.setenv("AGENT_SDK_SCIM_TOKEN", "scim-token")
    monkeypatch.setenv("AGENT_SDK_IDP_PROVIDER", "mock")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_auth_validate_mock(client):
    token_payload = {"sub": "user-1", "email": "u@example.com", "groups": ["admin"]}
    token = "mock:" + json.dumps(token_payload)
    resp = client.post("/auth/validate", json={"token": token})
    assert resp.status_code == 200
    data = resp.json()
    assert data["subject"] == "user-1"
    assert "admin" in data["groups"]


def test_admin_users_and_service_accounts(client):
    created = client.post(
        "/admin/users",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "name": "Alice"},
    )
    assert created.status_code == 200
    user = created.json()
    assert user["name"] == "Alice"

    svc = client.post(
        "/admin/service-accounts",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "name": "svc-bot"},
    )
    assert svc.status_code == 200
    assert svc.json()["is_service_account"] is True


def test_scim_provisioning(client):
    headers = {"Authorization": "Bearer scim-token"}
    create_payload = {
        "userName": "scim-user",
        "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User": {"orgId": "default"},
    }
    created = client.post("/scim/v2/Users", headers=headers, json=create_payload)
    assert created.status_code == 200
    user_id = created.json()["id"]

    listed = client.get("/scim/v2/Users", headers=headers)
    assert listed.status_code == 200
    assert any(user["id"] == user_id for user in listed.json()["Resources"])
