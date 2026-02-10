"""Tests for archive export and restore."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app
from agent_sdk.observability.stream_envelope import RunMetadata, SessionMetadata, RunStatus


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
    monkeypatch.setenv("API_KEY", "admin-key")
    monkeypatch.setenv("API_KEY_ROLE", "admin")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("AGENT_SDK_DB_PATH", os.path.join(tmpdir, "agent_sdk.db"))
        monkeypatch.setenv("AGENT_SDK_ARCHIVE_PATH", os.path.join(tmpdir, "archives"))
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_archive_export_and_restore(client):
    storage = client.app.state.storage
    storage.create_session(SessionMetadata(session_id="sess_arch", org_id="default"))
    storage.create_run(
        RunMetadata(
            run_id="run_arch",
            session_id="sess_arch",
            agent_id="planner-executor",
            org_id="default",
            status=RunStatus.COMPLETED,
        )
    )
    export = client.post(
        "/admin/archives/export",
        headers={"X-API-Key": "admin-key"},
        params={"run_id": "run_arch"},
    )
    assert export.status_code == 200
    path = export.json()["path"]

    storage.delete_run("run_arch")
    restore = client.post(
        "/admin/archives/restore",
        headers={"X-API-Key": "admin-key"},
        params={"path": path},
    )
    assert restore.status_code == 200
    assert storage.get_run("run_arch") is not None
