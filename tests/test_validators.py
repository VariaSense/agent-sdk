"""Tests for validators"""

import pytest
from pydantic import ValidationError
from agent_sdk.validators import (
    RunTaskRequest,
    ToolCallRequest,
    ModelConfigDict,
    ConfigSchema
)


def test_run_task_request_valid():
    """Test valid RunTaskRequest"""
    req = RunTaskRequest(task="Do something")
    assert req.task == "Do something"
    assert req.timeout == 300
    assert req.config is None


def test_run_task_request_empty_task():
    """Test RunTaskRequest with empty task"""
    with pytest.raises(ValidationError):
        RunTaskRequest(task="   ")  # Only whitespace


def test_run_task_request_task_too_long():
    """Test RunTaskRequest with task exceeding max length"""
    with pytest.raises(ValidationError):
        RunTaskRequest(task="x" * 10001)


def test_run_task_request_invalid_timeout():
    """Test RunTaskRequest with invalid timeout"""
    with pytest.raises(ValidationError):
        RunTaskRequest(task="test", timeout=0)  # Must be >= 1
    
    with pytest.raises(ValidationError):
        RunTaskRequest(task="test", timeout=3601)  # Must be <= 3600


def test_tool_call_request_valid():
    """Test valid ToolCallRequest"""
    req = ToolCallRequest(tool_name="search_web", inputs={"query": "python"})
    assert req.tool_name == "search_web"
    assert req.inputs == {"query": "python"}


def test_tool_call_request_invalid_tool_name():
    """Test ToolCallRequest with invalid tool name"""
    with pytest.raises(ValidationError):
        ToolCallRequest(tool_name="Tool-Name", inputs={})  # Invalid characters
    
    with pytest.raises(ValidationError):
        ToolCallRequest(tool_name="2toolname", inputs={})  # Can't start with number


def test_model_config_valid():
    """Test valid ModelConfigDict"""
    config = ModelConfigDict(
        name="gpt-4",
        provider="openai",
        model_id="gpt-4",
        temperature=0.7,
        max_tokens=2048
    )
    assert config.name == "gpt-4"
    assert config.temperature == 0.7


def test_model_config_invalid_temperature():
    """Test ModelConfigDict with invalid temperature"""
    with pytest.raises(ValidationError):
        ModelConfigDict(
            name="gpt-4",
            provider="openai",
            model_id="gpt-4",
            temperature=2.5  # Must be <= 2.0
        )


def test_config_schema_valid():
    """Test valid ConfigSchema"""
    config = ConfigSchema(
        models={
            "gpt4": ModelConfigDict(
                name="gpt-4",
                provider="openai",
                model_id="gpt-4"
            )
        },
        agents={"planner": {"model": "gpt4"}},
        rate_limits=[]
    )
    assert "gpt4" in config.models
    assert "planner" in config.agents


def test_config_schema_undefined_model_reference():
    """Test ConfigSchema with reference to undefined model"""
    with pytest.raises(ValidationError):
        ConfigSchema(
            models={
                "gpt4": ModelConfigDict(
                    name="gpt-4",
                    provider="openai",
                    model_id="gpt-4"
                )
            },
            agents={"planner": {"model": "undefined_model"}},
            rate_limits=[]
        )
