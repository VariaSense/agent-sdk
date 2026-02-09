"""Tests for prompt/policy registry endpoints."""

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
        db_path = os.path.join(tmpdir, "agent_sdk.db")
        monkeypatch.setenv("AGENT_SDK_DB_PATH", db_path)
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_prompt_policy_versioning(client):
    created = client.post(
        "/admin/policies",
        headers={"X-API-Key": "test-key"},
        json={"policy_id": "safety", "content": "v1"},
    )
    assert created.status_code == 200
    assert created.json()["version"] == 1

    created2 = client.post(
        "/admin/policies",
        headers={"X-API-Key": "test-key"},
        json={"policy_id": "safety", "content": "v2"},
    )
    assert created2.status_code == 200
    assert created2.json()["version"] == 2

    latest = client.get(
        "/admin/policies/safety/latest",
        headers={"X-API-Key": "test-key"},
    )
    assert latest.status_code == 200
    assert latest.json()["version"] == 2
