"""Tests for Python client SDK."""

import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from clients.python.agent_sdk_client import AgentSDKClient


def test_client_headers_and_payload():
    captured = {}

    def _request(method, path, payload=None):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        if path == "/v1/health":
            return {"version": "0.1.0"}
        return {"ok": True}

    client = AgentSDKClient("http://localhost:9000", api_key="key", org_id="org", request_func=_request)
    response = client.run_task("hello")

    assert response["ok"] is True
    assert captured["method"] == "POST"
    assert captured["path"] == "/run"
    assert captured["payload"]["task"] == "hello"

    compatibility = client.check_compatibility()
    assert compatibility["compatible"] is True
