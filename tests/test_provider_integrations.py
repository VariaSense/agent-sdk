"""Tests for provider clients and error normalization."""

from agent_sdk.config.model_config import ModelConfig
from agent_sdk.llm.providers.base import normalize_http_error
from agent_sdk.llm.providers.openai import OpenAIClient
from agent_sdk.llm.providers.anthropic import AnthropicClient
from agent_sdk.llm.providers.azure import AzureOpenAIClient


def test_normalize_http_error_retriable():
    err = normalize_http_error(429, {"error": {"code": "rate_limit", "message": "too many"}})
    assert err.retriable is True
    assert err.code == "rate_limit"


def test_openai_client_parse_response(monkeypatch):
    client = OpenAIClient(api_key="test", base_url="https://example.com")

    def _mock_request(payload):
        return {
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }

    monkeypatch.setattr(client, "_request", _mock_request)
    response = client.generate([{"role": "user", "content": "hi"}], ModelConfig(name="m", provider="x", model_id="gpt"))
    assert response.text == "hello"
    assert response.total_tokens == 3


def test_anthropic_client_parse_response(monkeypatch):
    client = AnthropicClient(api_key="test", base_url="https://example.com")

    def _mock_request(payload):
        return {
            "content": [{"text": "hi"}],
            "usage": {"input_tokens": 1, "output_tokens": 2},
        }

    monkeypatch.setattr(client, "_request", _mock_request)
    response = client.generate([{"role": "user", "content": "hi"}], ModelConfig(name="m", provider="x", model_id="claude"))
    assert response.text == "hi"
    assert response.total_tokens == 3


def test_azure_client_parse_response(monkeypatch):
    client = AzureOpenAIClient(api_key="test", endpoint="https://example.com")

    def _mock_request(deployment, payload):
        return {
            "choices": [{"message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }

    monkeypatch.setattr(client, "_request", _mock_request)
    response = client.generate([{"role": "user", "content": "hi"}], ModelConfig(name="m", provider="x", model_id="dep"))
    assert response.text == "hi"
