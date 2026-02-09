"""Tests for JWT auth."""

import base64
import hashlib
import hmac
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

import agent_sdk.security as security
from agent_sdk.server.app import create_app


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _make_jwt(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url(json.dumps(header).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


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
    secret = "test-secret"
    monkeypatch.setenv("AGENT_SDK_JWT_ENABLED", "true")
    monkeypatch.setenv("AGENT_SDK_JWT_SECRET", secret)
    monkeypatch.setenv("API_KEY", "test-key")
    security._api_key_manager = None
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(config_path=_write_config(tmpdir))
        client = TestClient(app)
        client.jwt_secret = secret
        yield client


def test_jwt_auth_allows_admin_access(client):
    token = _make_jwt(
        {"org_id": "default", "role": "admin", "scopes": ["*"]},
        client.jwt_secret,
    )
    response = client.get("/admin/orgs", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
