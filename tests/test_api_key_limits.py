"""Tests for API key rate limits and IP allowlists."""

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


def test_api_key_rate_limit_enforced(client):
    created = client.post(
        "/admin/api-keys",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "label": "limited", "role": "admin", "rate_limit_per_minute": 1},
    )
    assert created.status_code == 200
    key = created.json()["key"]

    ok = client.get("/admin/orgs", headers={"X-API-Key": key})
    assert ok.status_code == 200
    limited = client.get("/admin/orgs", headers={"X-API-Key": key})
    assert limited.status_code == 429


def test_ip_allowlist_enforced(client):
    created = client.post(
        "/admin/api-keys",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "label": "allow", "role": "admin", "ip_allowlist": ["1.2.3.4"]},
    )
    assert created.status_code == 200
    key = created.json()["key"]

    denied = client.get("/admin/orgs", headers={"X-API-Key": key})
    assert denied.status_code == 403
