"""Tests for webhook subscriptions and DLQ."""

import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

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


class _WebhookHandler(BaseHTTPRequestHandler):
    events = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        _WebhookHandler.events.append({"path": self.path, "body": body})
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return


@pytest.fixture
def server():
    server = HTTPServer(("localhost", 0), _WebhookHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield server
    server.shutdown()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_KEY", "admin-key")
    monkeypatch.setenv("API_KEY_ROLE", "admin")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_webhook_delivery_and_dlq(client, server):
    url = f"http://localhost:{server.server_port}/webhook"
    resp = client.post(
        "/admin/webhooks",
        headers={"X-API-Key": "admin-key"},
        json={"org_id": "default", "url": url, "event_types": ["run.completed"], "max_attempts": 1},
    )
    assert resp.status_code == 200

    run_resp = client.post(
        "/run",
        headers={"X-API-Key": "admin-key"},
        json={"task": "hello"},
    )
    assert run_resp.status_code == 200

    assert _WebhookHandler.events
    payload = json.loads(_WebhookHandler.events[-1]["body"])
    assert payload["event_type"] == "run.completed"

    resp_fail = client.post(
        "/admin/webhooks",
        headers={"X-API-Key": "admin-key"},
        json={"org_id": "default", "url": "http://localhost:1/fail", "event_types": ["run.completed"], "max_attempts": 1},
    )
    assert resp_fail.status_code == 200

    client.post(
        "/run",
        headers={"X-API-Key": "admin-key"},
        json={"task": "hello"},
    )
    dlq = client.get("/admin/webhooks/dlq", headers={"X-API-Key": "admin-key"})
    assert dlq.status_code == 200
    assert len(dlq.json()) >= 1
