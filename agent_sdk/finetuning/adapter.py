"""Adapter for fine-tuned models."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime, timezone


@dataclass
class AdapterConfig:
    """Configuration for model adapter.
    
    Attributes:
        adapter_name: Name of the adapter
        base_model: Base model this adapts
        adapter_type: Type of adapter (lora, prefix, etc.)
        hidden_dim: Hidden dimension for adapter
        dropout: Dropout rate
        scaling_factor: Scaling factor for adapter outputs
    """
    
    adapter_name: str = "default"
    base_model: str = "gpt-3.5-turbo"
    adapter_type: str = "lora"
    hidden_dim: int = 256
    dropout: float = 0.1
    scaling_factor: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "adapter_name": self.adapter_name,
            "base_model": self.base_model,
            "adapter_type": self.adapter_type,
            "hidden_dim": self.hidden_dim,
            "dropout": self.dropout,
            "scaling_factor": self.scaling_factor,
        }


class ModelAdapter:
    """Adapter for fine-tuned models.
    
    Wraps a fine-tuned model and provides a consistent interface
    for inference with optional preprocessing/postprocessing.
    """
    
    def __init__(self, model_id: str, config: Optional[AdapterConfig] = None):
        """Initialize adapter.
        
        Args:
            model_id: ID of fine-tuned model
            config: Adapter configuration
        """
        self.model_id = model_id
        self.config = config or AdapterConfig()
        self.created_at = datetime.now(timezone.utc)
        self.inference_count = 0
        self.total_tokens = 0
        self.is_active = True
    
    def activate(self) -> None:
        """Activate this adapter for inference."""
        self.is_active = True
    
    def deactivate(self) -> None:
        """Deactivate this adapter."""
        self.is_active = False
    
    def record_inference(self, tokens: int) -> None:
        """Record an inference call.
        
        Args:
            tokens: Number of tokens used
        """
        self.inference_count += 1
        self.total_tokens += tokens
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adapter usage statistics."""
        avg_tokens = self.total_tokens / max(1, self.inference_count)
        return {
            "model_id": self.model_id,
            "inference_count": self.inference_count,
            "total_tokens": self.total_tokens,
            "avg_tokens_per_inference": round(avg_tokens, 1),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "config": self.config.to_dict(),
            "created_at": self.created_at.isoformat(),
            "inference_count": self.inference_count,
            "total_tokens": self.total_tokens,
            "is_active": self.is_active,
        }
