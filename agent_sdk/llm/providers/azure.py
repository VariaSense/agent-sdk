"""Azure OpenAI provider client."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Dict, List

from agent_sdk.config.model_config import ModelConfig
from agent_sdk.llm.base import LLMClient, LLMResponse
from agent_sdk.llm.providers.base import ProviderError, normalize_http_error


class AzureOpenAIClient(LLMClient):
    def __init__(self, api_key: str, endpoint: str, api_version: str = "2024-02-15-preview"):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.api_version = api_version

    def _request(self, deployment: str, payload: Dict[str, object]) -> Dict[str, object]:
        url = f"{self.endpoint}/openai/deployments/{deployment}/chat/completions?api-version={self.api_version}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("api-key", self.api_key)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8") if err.fp else "{}"
            raise normalize_http_error(err.code, json.loads(body or "{}"))
        except Exception as exc:
            raise ProviderError(status_code=500, code="azure_request_failed", message=str(exc), retriable=True)

    def generate(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        payload = {
            "messages": messages,
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
        }
        response = self._request(model_config.model_id, payload)
        choices = response.get("choices", [])
        content = choices[0]["message"]["content"] if choices else ""
        usage = response.get("usage", {}) or {}
        return LLMResponse(
            text=content,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
        )


def create_azure_client() -> AzureOpenAIClient:
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not api_key or not endpoint:
        raise RuntimeError("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT are required")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    return AzureOpenAIClient(api_key=api_key, endpoint=endpoint, api_version=api_version)
