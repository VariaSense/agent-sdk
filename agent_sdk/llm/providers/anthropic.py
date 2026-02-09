"""Anthropic provider client."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Dict, List

from agent_sdk.config.model_config import ModelConfig
from agent_sdk.llm.base import LLMClient, LLMResponse
from agent_sdk.llm.providers.base import ProviderError, normalize_http_error


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(self, payload: Dict[str, object]) -> Dict[str, object]:
        url = f"{self.base_url}/messages"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("x-api-key", self.api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8") if err.fp else "{}"
            raise normalize_http_error(err.code, json.loads(body or "{}"))
        except Exception as exc:
            raise ProviderError(status_code=500, code="anthropic_request_failed", message=str(exc), retriable=True)

    def generate(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        payload = {
            "model": model_config.model_id,
            "max_tokens": model_config.max_tokens,
            "temperature": model_config.temperature,
            "messages": messages,
        }
        response = self._request(payload)
        content = ""
        if response.get("content"):
            content = response["content"][0].get("text", "")
        usage = response.get("usage", {}) or {}
        return LLMResponse(
            text=content,
            prompt_tokens=int(usage.get("input_tokens", 0)),
            completion_tokens=int(usage.get("output_tokens", 0)),
            total_tokens=int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0)),
        )


def create_anthropic_client() -> AnthropicClient:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required")
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
    return AnthropicClient(api_key=api_key, base_url=base_url)
