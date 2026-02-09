"""Tests for API key rotation and expiration."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

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


def test_api_key_rotation_invalidates_old_key(client):
    created = client.post(
        "/admin/api-keys",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "label": "rot", "role": "admin"},
    )
    assert created.status_code == 200
    data = created.json()
    old_key = data["key"]
    key_id = data["key_id"]

    rotated = client.post(
        f"/admin/api-keys/{key_id}/rotate",
        headers={"X-API-Key": "test-key"},
    )
    assert rotated.status_code == 200
    new_key = rotated.json()["key"]
    assert new_key != old_key

    denied = client.get("/admin/orgs", headers={"X-API-Key": old_key})
    assert denied.status_code == 401

    allowed = client.get("/admin/orgs", headers={"X-API-Key": new_key})
    assert allowed.status_code == 200


def test_api_key_expiration_blocks_access(client):
    expires_at = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    created = client.post(
        "/admin/api-keys",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "label": "exp", "expires_at": expires_at},
    )
    assert created.status_code == 200
    key = created.json()["key"]

    denied = client.get("/admin/orgs", headers={"X-API-Key": key})
    assert denied.status_code == 401
