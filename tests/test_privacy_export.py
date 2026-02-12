"""Tests for privacy export bundles."""

import os
import tempfile
import zipfile

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
        db_path = os.path.join(tmpdir, "agent_sdk.db")
        export_dir = os.path.join(tmpdir, "privacy_exports")
        monkeypatch.setenv("AGENT_SDK_DB_PATH", db_path)
        monkeypatch.setenv("AGENT_SDK_PRIVACY_EXPORT_PATH", export_dir)
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_privacy_export_bundle(client):
    run = client.post(
        "/run",
        headers={"X-API-Key": "test-key"},
        json={"task": "hello"},
    )
    assert run.status_code == 200
    export = client.post(
        "/admin/privacy/export",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default"},
    )
    assert export.status_code == 200
    path = export.json()["path"]
    assert os.path.exists(path)
    with zipfile.ZipFile(path, "r") as archive:
        assert "sessions.json" in archive.namelist()
        assert "runs.json" in archive.namelist()
