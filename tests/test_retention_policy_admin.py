"""Tests for per-tenant retention policy admin endpoints."""

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


def test_set_and_get_retention_policy(client):
    response = client.post(
        "/admin/retention",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "max_events": 50, "max_run_age_days": 7, "max_session_age_days": 30},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["org_id"] == "default"
    assert payload["max_events"] == 50
    assert payload["max_run_age_days"] == 7
    assert payload["max_session_age_days"] == 30

    fetched = client.get(
        "/admin/retention",
        headers={"X-API-Key": "test-key"},
        params={"org_id": "default"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["max_events"] == 50
