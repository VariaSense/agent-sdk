"""Tests for device registration endpoints."""

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


def test_device_register_and_pair(client):
    response = client.post(
        "/devices/register",
        headers={"X-API-Key": "test-key"},
        json={"name": "test-device"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "device_id" in data
    assert "pairing_code" in data

    pair = client.post(
        "/devices/pair",
        headers={"X-API-Key": "test-key"},
        json={
            "device_id": data["device_id"],
            "pairing_code": data["pairing_code"],
            "agent_id": "agent_1",
        },
    )
    assert pair.status_code == 200
    assert pair.json()["status"] == "paired"
