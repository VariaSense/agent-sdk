"""Multi-model support with routing, fallback, and cost tracking."""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ModelProvider(str, Enum):
    """Supported LLM providers."""
    
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    LOCAL = "local"
    MOCK = "mock"


@dataclass
class ModelConfig:
    """Configuration for an LLM model."""
    
    name: str
    provider: ModelProvider
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 1.0
    timeout_seconds: int = 30
    retry_count: int = 3
    cost_per_1k_input: float = 0.0  # USD
    cost_per_1k_output: float = 0.0  # USD
    extra_config: Dict[str, Any] = field(default_factory=dict)
    
    def merge(self, overrides: Dict[str, Any]) -> "ModelConfig":
        """Create a copy with overrides."""
        config = ModelConfig(
            name=self.name,
            provider=self.provider,
            max_tokens=overrides.get("max_tokens", self.max_tokens),
            temperature=overrides.get("temperature", self.temperature),
            top_p=overrides.get("top_p", self.top_p),
            timeout_seconds=overrides.get("timeout_seconds", self.timeout_seconds),
            retry_count=overrides.get("retry_count", self.retry_count),
            cost_per_1k_input=overrides.get("cost_per_1k_input", self.cost_per_1k_input),
            cost_per_1k_output=overrides.get("cost_per_1k_output", self.cost_per_1k_output),
            extra_config=overrides.get("extra_config", self.extra_config),
        )
        return config


@dataclass
class ModelUsageStats:
    """Track model usage and costs."""
    
    model_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    total_cost: float = 0.0
    latency_ms: float = 0.0
    
    def add_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_per_1k_input: float,
        cost_per_1k_output: float,
        latency_ms: float = 0.0
    ) -> None:
        """Record usage for a request."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_requests += 1
        
        # Calculate cost
        input_cost = (input_tokens / 1000) * cost_per_1k_input
        output_cost = (output_tokens / 1000) * cost_per_1k_output
        self.total_cost += input_cost + output_cost
        
        # Update latency (simple average)
        if latency_ms > 0:
            self.latency_ms = (self.latency_ms + latency_ms) / 2
    
    def record_failure(self) -> None:
        """Record a failed request."""
        self.failed_requests += 1
    
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return ((self.total_requests - self.failed_requests) / self.total_requests) * 100
    
    def avg_input_tokens(self) -> float:
        """Average input tokens per request."""
        if self.total_requests == 0:
            return 0.0
        return self.input_tokens / self.total_requests
    
    def avg_output_tokens(self) -> float:
        """Average output tokens per request."""
        if self.total_requests == 0:
            return 0.0
        return self.output_tokens / self.total_requests


@dataclass
class ModelSelection:
    """Result of model selection."""
    
    primary_model: ModelConfig
    fallback_models: List[ModelConfig] = field(default_factory=list)
    reason: str = ""


class ModelSelectionStrategy:
    """Strategy for selecting which model to use."""
    
    def select(
        self,
        available_models: List[ModelConfig],
        stats: Dict[str, ModelUsageStats],
        task_type: str = "general"
    ) -> ModelSelection:
        """Select model(s) for a task.
        
        Args:
            available_models: List of available models
            stats: Usage statistics for each model
            task_type: Type of task - "reasoning", "generation", "fast", "cost"
        
        Returns:
            ModelSelection with primary and fallback models
        """
        raise NotImplementedError


class CostOptimizedStrategy(ModelSelectionStrategy):
    """Select model that minimizes cost."""
    
    def select(
        self,
        available_models: List[ModelConfig],
        stats: Dict[str, ModelUsageStats],
        task_type: str = "general"
    ) -> ModelSelection:
        """Select cheapest available model."""
        if not available_models:
            raise ValueError("No models available")
        
        # Sort by cost
        sorted_models = sorted(
            available_models,
            key=lambda m: m.cost_per_1k_input + m.cost_per_1k_output
        )
        
        return ModelSelection(
            primary_model=sorted_models[0],
            fallback_models=sorted_models[1:],
            reason="Selected cheapest available model"
        )


class PerformanceOptimizedStrategy(ModelSelectionStrategy):
    """Select model that minimizes latency."""
    
    def select(
        self,
        available_models: List[ModelConfig],
        stats: Dict[str, ModelUsageStats],
        task_type: str = "general"
    ) -> ModelSelection:
        """Select fastest available model."""
        if not available_models:
            raise ValueError("No models available")
        
        # Sort by latency (use stats if available)
        def get_latency(model: ModelConfig) -> float:
            model_stats = stats.get(model.name)
            if model_stats:
                return model_stats.latency_ms
            return 0.0
        
        sorted_models = sorted(available_models, key=get_latency)
        
        return ModelSelection(
            primary_model=sorted_models[0],
            fallback_models=sorted_models[1:],
            reason="Selected fastest available model"
        )


class QualityOptimizedStrategy(ModelSelectionStrategy):
    """Select best quality model for task."""
    
    def select(
        self,
        available_models: List[ModelConfig],
        stats: Dict[str, ModelUsageStats],
        task_type: str = "general"
    ) -> ModelSelection:
        """Select best quality model for task type."""
        if not available_models:
            raise ValueError("No models available")
        
        # Quality ranking by task type
        quality_order = {
            "reasoning": ["gpt-4", "claude-3-opus", "gpt-3.5-turbo"],
            "generation": ["gpt-4", "claude-3-sonnet", "gpt-3.5-turbo"],
            "fast": ["gpt-3.5-turbo", "claude-3-haiku", "gpt-4"],
            "cost": ["gpt-3.5-turbo", "claude-3-haiku", "gpt-4"],
        }
        
        preferred_order = quality_order.get(task_type, quality_order["general"])
        
        # Sort models by quality preference
        def quality_rank(model: ModelConfig) -> int:
            for i, pref in enumerate(preferred_order):
                if pref.lower() in model.name.lower():
                    return i
            return len(preferred_order)
        
        sorted_models = sorted(available_models, key=quality_rank)
        
        return ModelSelection(
            primary_model=sorted_models[0],
            fallback_models=sorted_models[1:],
            reason=f"Selected best quality model for {task_type} task"
        )


class AdaptiveStrategy(ModelSelectionStrategy):
    """Adapt model selection based on cost, performance, and success rate."""
    
    def __init__(self, cost_weight: float = 0.3, performance_weight: float = 0.4, reliability_weight: float = 0.3):
        self.cost_weight = cost_weight
        self.performance_weight = performance_weight
        self.reliability_weight = reliability_weight
    
    def select(
        self,
        available_models: List[ModelConfig],
        stats: Dict[str, ModelUsageStats],
        task_type: str = "general"
    ) -> ModelSelection:
        """Select model based on adaptive scoring."""
        if not available_models:
            raise ValueError("No models available")
        
        scores = {}
        
        for model in available_models:
            model_stats = stats.get(model.name)
            
            # Cost score (lower is better)
            cost_score = (model.cost_per_1k_input + model.cost_per_1k_output) / 100
            
            # Performance score (lower latency is better)
            perf_score = model_stats.latency_ms / 1000 if model_stats else 0
            
            # Reliability score (success rate)
            rel_score = model_stats.success_rate() if model_stats else 100
            
            # Combine scores (normalize)
            combined_score = (
                (cost_score * self.cost_weight) +
                (perf_score * self.performance_weight) +
                ((100 - rel_score) * self.reliability_weight)
            )
            
            scores[model.name] = combined_score
        
        # Sort by score
        sorted_models = sorted(available_models, key=lambda m: scores[m.name])
        
        return ModelSelection(
            primary_model=sorted_models[0],
            fallback_models=sorted_models[1:],
            reason=f"Adaptive selection based on cost/performance/reliability"
        )


class ModelRouter:
    """Route requests to appropriate models with fallback support."""
    
    def __init__(self, strategy: Optional[ModelSelectionStrategy] = None):
        self.models: Dict[str, ModelConfig] = {}
        self.stats: Dict[str, ModelUsageStats] = {}
        self.strategy = strategy or CostOptimizedStrategy()
        self.max_fallbacks = 3
    
    def add_model(self, config: ModelConfig) -> None:
        """Register a model."""
        self.models[config.name] = config
        self.stats[config.name] = ModelUsageStats(model_name=config.name)
        logger.info(f"Registered model: {config.name}")
    
    def add_models(self, configs: List[ModelConfig]) -> None:
        """Register multiple models."""
        for config in configs:
            self.add_model(config)
    
    def select_models(self, task_type: str = "general") -> ModelSelection:
        """Select models for a task."""
        available = list(self.models.values())
        selection = self.strategy.select(available, self.stats, task_type)
        return selection
    
    def record_usage(
        self,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float = 0.0,
        success: bool = True
    ) -> None:
        """Record model usage and cost."""
        if model_name not in self.stats:
            return
        
        model_config = self.models.get(model_name)
        if not model_config:
            return
        
        stats = self.stats[model_name]
        
        if success:
            stats.add_usage(
                input_tokens,
                output_tokens,
                model_config.cost_per_1k_input,
                model_config.cost_per_1k_output,
                latency_ms
            )
        else:
            stats.record_failure()
    
    def get_stats(self, model_name: Optional[str] = None) -> Dict[str, ModelUsageStats]:
        """Get usage statistics."""
        if model_name:
            return {model_name: self.stats.get(model_name)} if model_name in self.stats else {}
        return self.stats.copy()
    
    def get_total_cost(self) -> float:
        """Get total cost across all models."""
        return sum(stats.total_cost for stats in self.stats.values())
    
    def get_cost_breakdown(self) -> Dict[str, float]:
        """Get cost breakdown by model."""
        return {name: stats.total_cost for name, stats in self.stats.items()}
    
    def switch_strategy(self, strategy: ModelSelectionStrategy) -> None:
        """Switch selection strategy."""
        self.strategy = strategy
        logger.info(f"Switched to {strategy.__class__.__name__}")


# Predefined model configurations

GPT_4 = ModelConfig(
    name="gpt-4",
    provider=ModelProvider.OPENAI,
    max_tokens=8192,
    temperature=0.7,
    cost_per_1k_input=0.03,
    cost_per_1k_output=0.06,
)

GPT_35_TURBO = ModelConfig(
    name="gpt-3.5-turbo",
    provider=ModelProvider.OPENAI,
    max_tokens=4096,
    temperature=0.7,
    cost_per_1k_input=0.001,
    cost_per_1k_output=0.002,
)

CLAUDE_3_OPUS = ModelConfig(
    name="claude-3-opus",
    provider=ModelProvider.ANTHROPIC,
    max_tokens=4096,
    temperature=0.7,
    cost_per_1k_input=0.015,
    cost_per_1k_output=0.075,
)

CLAUDE_3_SONNET = ModelConfig(
    name="claude-3-sonnet",
    provider=ModelProvider.ANTHROPIC,
    max_tokens=4096,
    temperature=0.7,
    cost_per_1k_input=0.003,
    cost_per_1k_output=0.015,
)

CLAUDE_3_HAIKU = ModelConfig(
    name="claude-3-haiku",
    provider=ModelProvider.ANTHROPIC,
    max_tokens=4096,
    temperature=0.7,
    cost_per_1k_input=0.00025,
    cost_per_1k_output=0.00125,
)


__all__ = [
    "ModelProvider",
    "ModelConfig",
    "ModelUsageStats",
    "ModelSelection",
    "ModelSelectionStrategy",
    "CostOptimizedStrategy",
    "PerformanceOptimizedStrategy",
    "QualityOptimizedStrategy",
    "AdaptiveStrategy",
    "ModelRouter",
    "GPT_4",
    "GPT_35_TURBO",
    "CLAUDE_3_OPUS",
    "CLAUDE_3_SONNET",
    "CLAUDE_3_HAIKU",
]
