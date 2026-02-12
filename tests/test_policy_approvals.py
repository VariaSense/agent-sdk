"""Tests for policy approval workflow."""

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


def test_policy_approval_listing(client):
    client.post(
        "/admin/policy-bundles",
        headers={"X-API-Key": "test-key"},
        json={"bundle_id": "approval-test", "content": {"tools": {"deny": ["filesystem.write"]}}},
    )
    submit = client.post(
        "/admin/policy-approvals",
        headers={"X-API-Key": "test-key"},
        json={"bundle_id": "approval-test", "version": 1},
    )
    assert submit.status_code == 200
    approvals = client.get(
        "/admin/policy-approvals",
        headers={"X-API-Key": "test-key"},
        params={"bundle_id": "approval-test"},
    )
    assert approvals.status_code == 200
    items = approvals.json()["approvals"]
    assert items and items[0]["bundle_id"] == "approval-test"
