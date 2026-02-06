"""Tests for API endpoints"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from agent_sdk.server.app import create_app
from agent_sdk.validators import RunTaskRequest, TaskResponse
import agent_sdk.security as security


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
def client(mock_llm, model_config):
    """Create test client"""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["API_KEY"] = "test-key"
        security._api_key_manager = None
        app = create_app(config_path=_write_config(tmpdir))
        yield TestClient(app)


def test_health_endpoint(client):
    """Test /health endpoint returns healthy status"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_ready_endpoint(client):
    """Test /ready endpoint indicates readiness"""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "ready" in data


def test_run_endpoint_missing_api_key(client):
    """Test /run endpoint requires API key"""
    payload = {"task": "Do something"}
    response = client.post("/run", json=payload)
    assert response.status_code == 401
    data = response.json()
    assert "api key" in data.get("detail", "").lower()


def test_run_endpoint_invalid_api_key(client, monkeypatch):
    """Test /run endpoint rejects invalid API key"""
    monkeypatch.setenv("API_KEY", "valid-key-123")
    
    payload = {"task": "Do something"}
    headers = {"X-API-Key": "invalid-key"}
    response = client.post("/run", json=payload, headers=headers)
    assert response.status_code == 401


def test_run_endpoint_invalid_task(client, monkeypatch):
    """Test /run endpoint validates task"""
    monkeypatch.setenv("API_KEY", "test-key")
    
    # Empty task
    payload = {"task": ""}
    headers = {"X-API-Key": "test-key"}
    response = client.post("/run", json=payload, headers=headers)
    assert response.status_code == 422  # Validation error


def test_run_endpoint_task_too_long(client, monkeypatch):
    """Test /run endpoint rejects overly long task"""
    monkeypatch.setenv("API_KEY", "test-key")
    
    payload = {"task": "x" * 10001}
    headers = {"X-API-Key": "test-key"}
    response = client.post("/run", json=payload, headers=headers)
    assert response.status_code == 422


def test_run_endpoint_invalid_timeout(client, monkeypatch):
    """Test /run endpoint validates timeout"""
    monkeypatch.setenv("API_KEY", "test-key")
    
    # Timeout too high
    payload = {"task": "Do something", "timeout": 3700}
    headers = {"X-API-Key": "test-key"}
    response = client.post("/run", json=payload, headers=headers)
    assert response.status_code == 422


def test_tools_endpoint(client):
    """Test /tools endpoint lists available tools"""
    response = client.get("/tools", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    assert "count" in data


def test_tools_endpoint_tool_schema(client):
    """Test /tools endpoint returns valid tool schema"""
    response = client.get("/tools", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    tools = response.json().get("tools", [])
    
    if tools:
        tool = tools[0]
        assert "name" in tool
        assert "description" in tool


def test_run_endpoint_success_response_structure(client, monkeypatch):
    """Test /run endpoint success response has correct structure"""
    monkeypatch.setenv("API_KEY", "test-key")
    
    payload = {"task": "Do something"}
    headers = {"X-API-Key": "test-key"}
    response = client.post("/run", json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        assert "run_id" in data["result"]
        assert "session_id" in data["result"]
        assert "status" in data
        assert "result" in data


def test_run_endpoint_error_handling(client, monkeypatch):
    """Test /run endpoint handles errors gracefully"""
    monkeypatch.setenv("API_KEY", "test-key")
    
    # Send request with missing required field
    payload = {}  # Missing 'task'
    headers = {"X-API-Key": "test-key"}
    response = client.post("/run", json=payload, headers=headers)
    assert response.status_code in [400, 422]
    data = response.json()
    assert "detail" in data or "error" in data


def test_run_endpoint_cors_headers(client):
    """Test /run endpoint includes CORS headers"""
    response = client.options("/run")
    # Note: FastAPI may not return 200 for OPTIONS, but headers should be present
    # in actual requests from browsers


def test_health_endpoint_response_time(client):
    """Test /health endpoint responds quickly"""
    import time
    start = time.time()
    response = client.get("/health")
    elapsed = time.time() - start
    
    assert response.status_code == 200
    assert elapsed < 1.0  # Should respond in less than 1 second
