"""
Tests for API key middleware on protected routes.
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
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_health_no_api_key_required(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_tools_requires_api_key(client):
    response = client.get("/tools")
    assert response.status_code == 401


def test_tools_allows_valid_api_key(client):
    response = client.get("/tools", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
