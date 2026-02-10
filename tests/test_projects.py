"""Tests for project/workspace entities and project-scoped keys."""

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
    monkeypatch.setenv("API_KEY", "admin-key")
    monkeypatch.setenv("API_KEY_ROLE", "admin")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_project_scoped_api_key_enforces_project(client):
    project = client.post(
        "/admin/projects",
        headers={"X-API-Key": "admin-key"},
        json={"org_id": "default", "name": "Alpha"},
    )
    assert project.status_code == 200
    project_id = project.json()["project_id"]

    key_resp = client.post(
        "/admin/api-keys",
        headers={"X-API-Key": "admin-key"},
        json={"org_id": "default", "label": "proj", "project_id": project_id},
    )
    assert key_resp.status_code == 200
    project_key = key_resp.json()["key"]

    run_resp = client.post(
        "/run",
        headers={"X-API-Key": project_key},
        json={"task": "hello"},
    )
    assert run_resp.status_code == 200

    storage = client.app.state.storage
    runs = storage.list_runs(org_id="default", limit=5)
    assert any(run.tags.get("project_id") == project_id for run in runs)
