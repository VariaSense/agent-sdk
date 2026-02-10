"""Tests for residency and encryption controls."""

import os
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app
from agent_sdk.encryption import generate_key
from agent_sdk.storage.sqlite import SQLiteStorage
from agent_sdk.observability.stream_envelope import SessionMetadata


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
    monkeypatch.setenv("AGENT_SDK_DATA_REGION", "us-east")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_residency_enforced(client):
    set_residency = client.post(
        "/admin/residency",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "region": "eu-west"},
    )
    assert set_residency.status_code == 200
    response = client.post(
        "/run",
        headers={"X-API-Key": "test-key"},
        json={"task": "hello"},
    )
    assert response.status_code == 409


def test_encryption_at_rest(tmp_path):
    db_path = tmp_path / "enc.db"
    key = generate_key()
    storage = SQLiteStorage(str(db_path), encryption_resolver=lambda org_id: key)
    session = SessionMetadata(session_id="sess_1", org_id="default", user_id="user")
    storage.create_session(session)
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT tags_json, metadata_json FROM sessions WHERE session_id = ?", ("sess_1",)).fetchone()
    assert row is not None
    assert "__encrypted__" in row[0] or "__encrypted__" in row[1]


def test_encryption_key_admin(client):
    response = client.post(
        "/admin/encryption-keys",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "key": None},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["org_id"] == "default"
    assert payload["key"]
