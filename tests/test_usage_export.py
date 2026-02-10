"""Tests for usage export with cost allocation tags."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app
from agent_sdk.observability.stream_envelope import SessionMetadata, RunMetadata, RunStatus


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
        monkeypatch.setenv("AGENT_SDK_DB_PATH", os.path.join(tmpdir, "agent_sdk.db"))
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_usage_export_grouped_by_project(client):
    storage = client.app.state.storage
    storage.create_session(SessionMetadata(session_id="sess_1", org_id="default"))
    storage.create_run(
        RunMetadata(
            run_id="run_1",
            session_id="sess_1",
            agent_id="planner-executor",
            org_id="default",
            status=RunStatus.COMPLETED,
            tags={"project": "alpha"},
            metadata={"token_count": 42},
        )
    )
    response = client.get(
        "/admin/usage/export",
        headers={"X-API-Key": "test-key"},
        params={"group_by": "org_id,project"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    row = payload["results"][0]
    assert row["org_id"] == "default"
    assert row["project"] == "alpha"
    assert row["token_count"] == 42
