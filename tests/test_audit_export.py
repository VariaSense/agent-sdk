"""Tests for audit log export and hash chaining."""

import os
import tempfile
import json

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
    monkeypatch.setenv("AGENT_SDK_AUDIT_HASH_CHAIN", "1")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        audit_path = os.path.join(tmpdir, "audit.jsonl")
        monkeypatch.setenv("AGENT_SDK_AUDIT_LOG_PATH", audit_path)
        app = create_app(config_path=_write_config(tmpdir))
        client = TestClient(app)
        client.audit_path = audit_path
        yield client


def test_audit_export_jsonl_and_csv(client):
    create_key = client.post(
        "/admin/api-keys",
        headers={"X-API-Key": "test-key"},
        json={"org_id": "default", "label": "audit-export"},
    )
    assert create_key.status_code == 200

    export_jsonl = client.get(
        "/admin/audit-logs/export",
        headers={"X-API-Key": "test-key"},
        params={"format": "jsonl"},
    )
    assert export_jsonl.status_code == 200
    lines = [line for line in export_jsonl.text.splitlines() if line.strip()]
    payloads = [json.loads(line) for line in lines]
    assert any(entry.get("hash") for entry in payloads)
    assert any(entry.get("action", "").startswith("admin.") for entry in payloads)

    export_csv = client.get(
        "/admin/audit-logs/export",
        headers={"X-API-Key": "test-key"},
        params={"format": "csv"},
    )
    assert export_csv.status_code == 200
    header = export_csv.text.splitlines()[0]
    assert header.startswith("timestamp,action,actor,org_id")
