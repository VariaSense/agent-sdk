"""Tests for exception handling and custom exception types"""

import pytest
from agent_sdk.exceptions import (
    AgentSDKException,
    ConfigError,
    RateLimitError,
    ToolError,
    LLMError,
    ValidationError,
    TimeoutError
)


def test_agent_sdk_exception_base():
    """Test base AgentSDKException"""
    exc = AgentSDKException("Test error")
    assert str(exc) == "Test error"
    assert exc.message == "Test error"


def test_agent_sdk_exception_with_code():
    """Test AgentSDKException with error code"""
    exc = AgentSDKException("Test error", code="TEST_ERROR")
    assert str(exc) == "[TEST_ERROR] Test error"
    assert exc.code == "TEST_ERROR"


def test_config_error():
    """Test ConfigError"""
    with pytest.raises(ConfigError):
        raise ConfigError("Config not found")


def test_rate_limit_error():
    """Test RateLimitError"""
    with pytest.raises(RateLimitError):
        raise RateLimitError("Rate limit exceeded", code="RATE_LIMIT_EXCEEDED")


def test_tool_error():
    """Test ToolError"""
    with pytest.raises(ToolError):
        raise ToolError("Tool execution failed")


def test_llm_error():
    """Test LLMError"""
    with pytest.raises(LLMError):
        raise LLMError("API call failed")


def test_validation_error():
    """Test ValidationError"""
    with pytest.raises(ValidationError):
        raise ValidationError("Invalid input")


def test_timeout_error():
    """Test TimeoutError"""
    with pytest.raises(TimeoutError):
        raise TimeoutError("Operation timed out")


def test_exception_context():
    """Test exception with context data"""
    context_data = {"model": "gpt-4", "tokens": 100}
    exc = LLMError("API call failed", context=context_data)
    assert exc.context == context_data


def test_exception_inheritance():
    """Test exception inheritance chain"""
    exc = ConfigError("Test")
    assert isinstance(exc, AgentSDKException)
    assert isinstance(exc, Exception)
