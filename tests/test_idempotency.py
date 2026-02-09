"""Tests for idempotency keys on run creation."""

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


def test_idempotency_key_reuses_response(client):
    headers = {"X-API-Key": "test-key", "Idempotency-Key": "idem-1"}
    first = client.post("/run", headers=headers, json={"task": "hello"})
    assert first.status_code == 200
    second = client.post("/run", headers=headers, json={"task": "hello"})
    assert second.status_code == 200
    assert first.json()["result"]["run_id"] == second.json()["result"]["run_id"]
    assert first.json()["result"]["session_id"] == second.json()["result"]["session_id"]
