"""Tests for deterministic testing mocks."""

from agent_sdk.testing.mocks import DeterministicLLMClient, ToolMock
from agent_sdk.config.model_config import ModelConfig


def test_deterministic_llm_returns_sequence():
    llm = DeterministicLLMClient(responses=["first", "second"])
    model = ModelConfig(name="test-model", provider="openai", model_id="gpt-4")
    messages = [{"role": "user", "content": "hello"}]

    first = llm.generate(messages, model)
    second = llm.generate(messages, model)
    third = llm.generate(messages, model)

    assert first.text == "first"
    assert second.text == "second"
    assert third.text == "second"
    assert len(llm.calls) == 3


def test_tool_mock_tracks_calls_and_outputs():
    tool = ToolMock(outputs=["a", "b"])

    assert tool({"x": 1}) == "a"
    assert tool({"x": 2}) == "b"
    assert tool({"x": 3}) == "b"
    assert tool.calls == [{"x": 1}, {"x": 2}, {"x": 3}]
