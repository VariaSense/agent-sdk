"""
Tests for run and session endpoints.
"""

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


def test_run_and_session_endpoints(client):
    headers = {"X-API-Key": "test-key"}
    response = client.post("/run", json={"task": "hello"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    result = data.get("result", {})
    run_id = result.get("run_id")
    session_id = result.get("session_id")

    assert run_id
    assert session_id

    run_response = client.get(f"/run/{run_id}", headers=headers)
    assert run_response.status_code == 200
    run_data = run_response.json()
    assert run_data["run_id"] == run_id
    assert run_data["session_id"] == session_id
    assert run_data["status"] in {"completed", "error", "running"}

    sessions_response = client.get("/sessions", headers=headers)
    assert sessions_response.status_code == 200
    sessions = sessions_response.json()
    assert any(s["session_id"] == session_id for s in sessions)

    session_response = client.get(f"/sessions/{session_id}", headers=headers)
    assert session_response.status_code == 200
    session_data = session_response.json()
    assert session_data["session_id"] == session_id
