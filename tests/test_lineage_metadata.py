"""Tests for lineage metadata capture on runs."""

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
        app = create_app(config_path=_write_config(tmpdir), storage_path=db_path)
        yield TestClient(app)


def test_run_lineage_metadata(client):
    headers = {"X-API-Key": "test-key"}
    lineage = {"source": "jira", "ticket": "AGENT-123", "parents": ["run_0"]}
    response = client.post(
        "/run",
        json={"task": "hello", "lineage": lineage},
        headers=headers,
    )
    assert response.status_code == 200
    run_id = response.json()["result"]["run_id"]
    run_response = client.get(f"/run/{run_id}", headers=headers)
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert run_data["metadata"]["lineage"] == lineage
