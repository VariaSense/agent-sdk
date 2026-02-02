from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ModelConfig:
    name: str
    provider: str
    model_id: str
    temperature: float = 0.2
    max_tokens: int = 1024
    extra: Dict[str, Any] = None
