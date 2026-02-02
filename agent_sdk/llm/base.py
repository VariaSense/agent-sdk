from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict
from agent_sdk.config.model_config import ModelConfig

@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMClient(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        ...

    async def generate_async(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        import asyncio
        return await asyncio.to_thread(self.generate, messages, model_config)
