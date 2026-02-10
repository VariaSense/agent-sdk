"""Basic contract checks for /v1 API paths."""

import os
import tempfile

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


def test_v1_run_endpoint():
    with tempfile.TemporaryDirectory() as tmpdir:
        security._api_key_manager = None
        os.environ["API_KEY"] = "test-key"
        app = create_app(config_path=_write_config(tmpdir))
        client = TestClient(app)
        response = client.post(
            "/v1/run",
            headers={"X-API-Key": "test-key"},
            json={"task": "hello"},
        )
        assert response.status_code == 200
        assert response.headers.get("X-API-Version") == "v1"
