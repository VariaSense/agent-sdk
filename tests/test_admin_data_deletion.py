"""Tests for admin data deletion and retention endpoints."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app
from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    RunStatus,
    SessionMetadata,
    StreamEnvelope,
    StreamChannel,
)


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


def _seed_run(client: TestClient, run_id: str, session_id: str) -> None:
    storage = client.app.state.storage
    storage.create_session(SessionMetadata(session_id=session_id, org_id="default"))
    storage.create_run(
        RunMetadata(
            run_id=run_id,
            session_id=session_id,
            agent_id="agent",
            org_id="default",
            status=RunStatus.RUNNING,
        )
    )
    for seq in range(3):
        storage.append_event(
            StreamEnvelope(
                run_id=run_id,
                session_id=session_id,
                stream=StreamChannel.ASSISTANT,
                event="message",
                payload={"text": f"msg-{seq}"},
                seq=seq,
                status=RunStatus.RUNNING.value,
                metadata={"org_id": "default"},
            )
        )


def test_purge_run_events(client):
    _seed_run(client, "run_purge", "sess_purge")
    response = client.post(
        "/admin/runs/run_purge/events/purge",
        headers={"X-API-Key": "test-key", "X-Org-Id": "default"},
        json={"before_seq": 2},
    )
    assert response.status_code == 200
    storage = client.app.state.storage
    remaining = storage.list_events("run_purge")
    assert [event.seq for event in remaining] == [2]


def test_delete_run_and_session(client):
    _seed_run(client, "run_delete", "sess_delete")
    delete_run = client.delete(
        "/admin/runs/run_delete",
        headers={"X-API-Key": "test-key", "X-Org-Id": "default"},
    )
    assert delete_run.status_code == 200
    storage = client.app.state.storage
    assert storage.get_run("run_delete") is None

    _seed_run(client, "run_delete2", "sess_delete2")
    delete_session = client.delete(
        "/admin/sessions/sess_delete2",
        headers={"X-API-Key": "test-key", "X-Org-Id": "default"},
    )
    assert delete_session.status_code == 200
    assert storage.get_session("sess_delete2") is None
