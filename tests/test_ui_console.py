"""
Tests for dev console UI endpoint.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app
from agent_sdk.ui.build import build_ui


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


def test_ui_endpoint_serves_html(client):
    response = client.get("/ui")
    assert response.status_code == 200
    assert "Agent SDK Dev Console" in response.text


def test_ui_root_serves_built_html(client):
    build_path = build_ui()
    assert build_path.endswith("agent_sdk/ui/dist/index.html")
    response = client.get("/")
    assert response.status_code == 200
    assert "Agent SDK Dev Console" in response.text
