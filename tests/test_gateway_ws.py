"""Tests for gateway WebSocket server."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app
from agent_sdk.observability.stream_envelope import StreamEnvelope, StreamChannel


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


def _auth(ws):
    ws.send_json({"type": "auth", "request_id": "req-1", "payload": {"api_key": "test-key"}})
    response = ws.receive_json()
    assert response["type"] == "ack"


def test_gateway_requires_auth(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "subscribe", "payload": {"run_id": "run_missing"}})
        response = ws.receive_json()
        assert response["type"] == "error"
        assert response["payload"]["code"] in {"AUTH_REQUIRED", "AUTH_FAILED"}


def test_gateway_subscribe_multi_client(client):
    run_id = "run_ws_test"
    store = client.app.state.run_store
    store.create_run(run_id)
    store.append_event(
        run_id,
        StreamEnvelope(
            run_id=run_id,
            session_id="sess_1",
            stream=StreamChannel.LIFECYCLE,
            event="start",
            payload={"task": "hello"},
            seq=0,
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
            seq=1,
        ),
    )

    with client.websocket_connect("/ws") as ws1, client.websocket_connect("/ws") as ws2:
        _auth(ws1)
        _auth(ws2)

        ws1.send_json({"type": "subscribe", "request_id": "sub-1", "payload": {"run_id": run_id}})
        ws2.send_json({"type": "subscribe", "request_id": "sub-2", "payload": {"run_id": run_id}})

        ack1 = ws1.receive_json()
        ack2 = ws2.receive_json()
        assert ack1["type"] == "ack"
        assert ack2["type"] == "ack"

        event1 = ws1.receive_json()
        event2 = ws2.receive_json()
        assert event1["type"] == "event"
        assert event2["type"] == "event"
        assert event1["payload"]["run_id"] == run_id
        assert event2["payload"]["run_id"] == run_id
