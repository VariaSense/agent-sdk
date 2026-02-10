"""Tests for governance policy bundle admin endpoints."""

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


def test_policy_bundle_create_and_assign(client):
    create_resp = client.post(
        "/admin/policy-bundles",
        headers={"X-API-Key": "test-key"},
        json={
            "bundle_id": "default-policy",
            "description": "Default governance policy",
            "content": {"tools": {"deny": ["filesystem.write"]}},
        },
    )
    assert create_resp.status_code == 200
    payload = create_resp.json()
    assert payload["bundle_id"] == "default-policy"
    assert payload["version"] == 1

    list_resp = client.get("/admin/policy-bundles", headers={"X-API-Key": "test-key"})
    assert list_resp.status_code == 200
    bundles = list_resp.json()["bundles"]
    assert any(bundle["bundle_id"] == "default-policy" for bundle in bundles)

    versions_resp = client.get(
        "/admin/policy-bundles/default-policy", headers={"X-API-Key": "test-key"}
    )
    assert versions_resp.status_code == 200
    versions = versions_resp.json()["versions"]
    assert len(versions) == 1
    assert versions[0]["version"] == 1

    assign_resp = client.post(
        "/admin/policy-assignments",
        headers={"X-API-Key": "test-key"},
        json={
            "org_id": "default",
            "bundle_id": "default-policy",
            "version": 1,
            "overrides": {"tools": {"allow": ["filesystem.read"]}},
        },
    )
    assert assign_resp.status_code == 200
    assignment = assign_resp.json()
    assert assignment["org_id"] == "default"
    assert assignment["bundle_id"] == "default-policy"

    get_assign = client.get(
        "/admin/policy-assignments",
        headers={"X-API-Key": "test-key"},
        params={"org_id": "default"},
    )
    assert get_assign.status_code == 200
    assert get_assign.json()["assignment"]["bundle_id"] == "default-policy"
