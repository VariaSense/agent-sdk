from typing import List, Dict
from agent_sdk.config.model_config import ModelConfig
from .base import LLMClient, LLMResponse

class MockLLMClient(LLMClient):
    def generate(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        last = messages[-1]["content"]
        text = f"[{model_config.name}] {last}"
        prompt_tokens = sum(len(m["content"].split()) for m in messages)
        completion_tokens = len(text.split())
        total_tokens = prompt_tokens + completion_tokens
        return LLMResponse(text, prompt_tokens, completion_tokens, total_tokens)
