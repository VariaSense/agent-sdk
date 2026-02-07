"""Tests for event replay endpoint."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app
from agent_sdk.observability.stream_envelope import StreamEnvelope, StreamChannel, SessionMetadata, RunMetadata, RunStatus


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
    monkeypatch.setenv("API_KEY_ROLE", "admin")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("AGENT_SDK_DB_PATH", os.path.join(tmpdir, "agent_sdk.db"))
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_replay_endpoint_returns_events(client):
    storage = client.app.state.storage
    run_store = client.app.state.run_store

    storage.create_session(SessionMetadata(session_id="sess_1", org_id="default"))
    storage.create_run(
        RunMetadata(
            run_id="run_replay",
            session_id="sess_1",
            agent_id="planner-executor",
            org_id="default",
            status=RunStatus.RUNNING,
        )
    )
    run_store.create_run("run_replay")
    run_store.append_event(
        "run_replay",
        StreamEnvelope(
            run_id="run_replay",
            session_id="sess_1",
            stream=StreamChannel.LIFECYCLE,
            event="start",
            payload={"task": "hi"},
            seq=0,
            metadata={"org_id": "default"},
        ),
    )
    run_store.append_event(
        "run_replay",
        StreamEnvelope(
            run_id="run_replay",
            session_id="sess_1",
            stream=StreamChannel.LIFECYCLE,
            event="end",
            payload={"status": "completed"},
            seq=1,
            metadata={"org_id": "default"},
        ),
    )

    response = client.get(
        "/run/run_replay/events/replay",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
