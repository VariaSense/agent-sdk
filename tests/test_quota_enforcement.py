"""Tests for quota enforcement on runs."""

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
        db_path = os.path.join(tmpdir, "agent_sdk.db")
        monkeypatch.setenv("AGENT_SDK_DB_PATH", db_path)
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_quota_blocks_runs(client):
    quota = client.post(
        "/admin/quotas",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "max_runs": 0},
    )
    assert quota.status_code == 200

    response = client.post(
        "/run",
        headers={"X-API-Key": "test-key"},
        json={"task": "hello"},
    )
    assert response.status_code == 429


def test_project_quota_blocks_runs(client):
    project = client.post(
        "/admin/projects",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "name": "Quota Project"},
    )
    assert project.status_code == 200
    project_id = project.json()["project_id"]
    key_resp = client.post(
        "/admin/api-keys",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "project_id": project_id, "label": "project-key"},
    )
    assert key_resp.status_code == 200
    project_key = key_resp.json()["key"]
    quota = client.post(
        "/admin/quotas/projects",
        headers={"X-API-Key": "test-key"},
        json={"project_id": project_id, "max_runs": 0},
    )
    assert quota.status_code == 200
    response = client.post(
        "/run",
        headers={"X-API-Key": project_key},
        json={"task": "hello"},
    )
    assert response.status_code == 429


def test_api_key_quota_blocks_runs(client):
    key_resp = client.post(
        "/admin/api-keys",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "label": "key-quota"},
    )
    assert key_resp.status_code == 200
    key = key_resp.json()["key"]
    quota = client.post(
        "/admin/quotas/api-keys",
        headers={"X-API-Key": "test-key"},
        json={"key": key, "max_runs": 0},
    )
    assert quota.status_code == 200
    response = client.post(
        "/run",
        headers={"X-API-Key": key},
        json={"task": "hello"},
    )
    assert response.status_code == 429
