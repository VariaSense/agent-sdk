"""Tests for org scoping on run/session access."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app
from agent_sdk.observability.stream_envelope import SessionMetadata, RunMetadata, RunStatus, StreamEnvelope, StreamChannel


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


def test_run_access_scoped_by_org(client):
    storage = client.app.state.storage
    storage.create_session(SessionMetadata(session_id="sess_alpha", org_id="alpha"))
    storage.create_run(
        RunMetadata(
            run_id="run_alpha",
            session_id="sess_alpha",
            agent_id="planner-executor",
            org_id="alpha",
            status=RunStatus.RUNNING,
        )
    )

    denied = client.get(
        "/run/run_alpha",
        headers={"X-API-Key": "test-key", "X-Org-Id": "beta"},
    )
    assert denied.status_code == 403

    allowed = client.get(
        "/run/run_alpha",
        headers={"X-API-Key": "test-key", "X-Org-Id": "alpha"},
    )
    assert allowed.status_code == 200


def test_session_list_scoped_by_org(client):
    storage = client.app.state.storage
    storage.create_session(SessionMetadata(session_id="sess_alpha", org_id="alpha"))
    storage.create_session(SessionMetadata(session_id="sess_beta", org_id="beta"))

    response = client.get(
        "/sessions",
        headers={"X-API-Key": "test-key", "X-Org-Id": "alpha"},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(session["org_id"] == "alpha" for session in data)


def test_run_events_scoped_by_org(client):
    storage = client.app.state.storage
    run_store = client.app.state.run_store
    storage.create_session(SessionMetadata(session_id="sess_alpha", org_id="alpha"))
    storage.create_run(
        RunMetadata(
            run_id="run_alpha",
            session_id="sess_alpha",
            agent_id="planner-executor",
            org_id="alpha",
            status=RunStatus.RUNNING,
        )
    )
    run_store.create_run("run_alpha")
    run_store.append_event(
        "run_alpha",
        StreamEnvelope(
            run_id="run_alpha",
            session_id="sess_alpha",
            stream=StreamChannel.LIFECYCLE,
            event="start",
            payload={"task": "hi"},
            seq=0,
            metadata={"org_id": "alpha"},
        ),
    )
    run_store.append_event(
        "run_alpha",
        StreamEnvelope(
            run_id="run_alpha",
            session_id="sess_alpha",
            stream=StreamChannel.LIFECYCLE,
            event="end",
            payload={"status": "completed"},
            seq=1,
            metadata={"org_id": "alpha"},
        ),
    )

    denied = client.get(
        "/run/run_alpha/events",
        headers={"X-API-Key": "test-key", "X-Org-Id": "beta"},
    )
    assert denied.status_code == 403

    with client.stream(
        "GET",
        "/run/run_alpha/events",
        headers={"X-API-Key": "test-key", "X-Org-Id": "alpha"},
    ) as allowed:
        assert allowed.status_code == 200
