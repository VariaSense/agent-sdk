"""Tests for schedule admin endpoints."""

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


def test_create_and_list_schedule(client):
    created = client.post(
        "/admin/schedules",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "task": "ping", "cron": "*/5 * * * *"},
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["org_id"] == "default"
    assert payload["cron"] == "*/5 * * * *"

    listing = client.get("/admin/schedules", headers={"X-API-Key": "test-key"})
    assert listing.status_code == 200
    assert any(entry["schedule_id"] == payload["schedule_id"] for entry in listing.json())
