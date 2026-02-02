"""Test suite for Agent SDK - Shared fixtures and configuration"""

import pytest
from agent_sdk import AgentContext, Tool, GLOBAL_TOOL_REGISTRY
from agent_sdk.config.model_config import ModelConfig
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.observability.bus import EventBus


@pytest.fixture
def mock_llm():
    """Fixture providing MockLLMClient"""
    return MockLLMClient()


@pytest.fixture
def model_config():
    """Fixture providing default ModelConfig"""
    return ModelConfig(
        name="test-gpt4",
        provider="openai",
        model_id="gpt-4",
        temperature=0.7,
        max_tokens=2048
    )


@pytest.fixture
def agent_context(model_config):
    """Fixture providing AgentContext with defaults"""
    return AgentContext(
        tools={},
        model_config=model_config,
        events=None,
        rate_limiter=None,
        max_short_term=100,
        max_long_term=1000
    )


@pytest.fixture
def event_bus():
    """Fixture providing EventBus"""
    return EventBus([])


@pytest.fixture
def sample_tool():
    """Fixture providing a sample echo tool"""
    tool = Tool(
        name="test_echo",
        description="Echo back input",
        func=lambda args: args.get("text", "")
    )
    GLOBAL_TOOL_REGISTRY.register(tool)
    yield tool
    # Cleanup
    if tool.name in GLOBAL_TOOL_REGISTRY.tools:
        del GLOBAL_TOOL_REGISTRY.tools[tool.name]
