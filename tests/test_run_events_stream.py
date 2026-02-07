"""
Tests for run events SSE streaming endpoint.
"""

import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from agent_sdk.server.app import create_app
import agent_sdk.security as security
from agent_sdk.observability.stream_envelope import (
    StreamEnvelope,
    StreamChannel,
    SessionMetadata,
    RunMetadata,
    RunStatus,
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
        monkeypatch.setenv("AGENT_SDK_DB_PATH", os.path.join(tmpdir, "agent_sdk.db"))
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def _parse_sse_line(line: str):
    assert line.startswith("data: ")
    return json.loads(line.replace("data: ", "", 1))


def test_run_events_stream_not_found(client):
    response = client.get("/run/run_missing/events", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404


def test_run_events_stream_returns_events(client):
    run_id = "run_test"
    store = client.app.state.run_store
    store.create_run(run_id)
    storage = client.app.state.storage
    storage.create_session(SessionMetadata(session_id="sess_1", org_id="default"))
    storage.create_run(
        RunMetadata(
            run_id=run_id,
            session_id="sess_1",
            agent_id="planner-executor",
            org_id="default",
            status=RunStatus.RUNNING,
        )
    )

    store.append_event(
        run_id,
        StreamEnvelope(
            run_id=run_id,
            session_id="sess_1",
            stream=StreamChannel.LIFECYCLE,
            event="start",
            payload={"task": "hi"},
        ),
    )
    store.append_event(
        run_id,
        StreamEnvelope(
            run_id=run_id,
            session_id="sess_1",
            stream=StreamChannel.LIFECYCLE,
            event="end",
            payload={"status": "completed"},
        ),
    )

    with client.stream("GET", f"/run/{run_id}/events", headers={"X-API-Key": "test-key"}) as response:
        assert response.status_code == 200
        lines = []
        for line in response.iter_lines():
            if line:
                lines.append(line if isinstance(line, str) else line.decode())
            if len(lines) >= 2:
                break

    first = _parse_sse_line(lines[0])
    second = _parse_sse_line(lines[1])

    assert first["run_id"] == run_id
    assert first["event"] == "start"
    assert second["event"] == "end"
