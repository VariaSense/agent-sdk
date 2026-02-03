"""Model routing with fallback and cost tracking."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import time


class RoutingStrategy(Enum):
    """Model selection strategy."""
    
    FASTEST = "fastest"              # Prioritize speed and cost
    MOST_CAPABLE = "most_capable"    # Prioritize reasoning capability
    BALANCED = "balanced"             # Balance cost and capability
    COST_OPTIMIZED = "cost_optimized" # Minimize cost
    ROUND_ROBIN = "round_robin"       # Rotate through models
    CUSTOM = "custom"                 # User-defined function


@dataclass
class ModelUsageMetrics:
    """Metrics for a model usage."""
    
    model_id: str
    tokens_used: int = 0
    cost: float = 0.0
    request_count: int = 0
    error_count: int = 0
    latency_ms: float = 0.0
    success_rate: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "tokens_used": self.tokens_used,
            "cost": self.cost,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "latency_ms": self.latency_ms,
            "success_rate": self.success_rate
        }


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""
    
    enabled: bool = True
    max_retries: int = 3
    retry_delay_ms: float = 100.0
    backoff_multiplier: float = 1.5
    fallback_models: List[str] = field(default_factory=list)
    
    # Trigger conditions
    on_rate_limit: bool = True
    on_timeout: bool = True
    on_error: bool = True
    on_insufficient_context: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "max_retries": self.max_retries,
            "retry_delay_ms": self.retry_delay_ms,
            "backoff_multiplier": self.backoff_multiplier,
            "fallback_models": self.fallback_models,
            "on_rate_limit": self.on_rate_limit,
            "on_timeout": self.on_timeout,
            "on_error": self.on_error,
            "on_insufficient_context": self.on_insufficient_context
        }


class ModelRouter:
    """Routes requests to optimal LLM model."""
    
    def __init__(self, strategy: RoutingStrategy = RoutingStrategy.BALANCED,
                 provider_manager: Optional[Any] = None):
        """Initialize router.
        
        Args:
            strategy: Model selection strategy
            provider_manager: Provider manager instance
        """
        self.strategy = strategy
        self.provider_manager = provider_manager
        
        # Routing state
        self.usage_metrics: Dict[str, ModelUsageMetrics] = {}
        self.fallback_config = FallbackConfig()
        self.custom_router: Optional[Callable] = None
        self.round_robin_index = 0
    
    def select_model(self, 
                    available_models: List[str],
                    task_description: Optional[str] = None,
                    context_tokens: int = 0) -> str:
        """Select best model for task.
        
        Args:
            available_models: List of available model IDs
            task_description: Description of task
            context_tokens: Number of context tokens needed
        
        Returns:
            Selected model ID
        """
        if not available_models:
            raise ValueError("No available models")
        
        if len(available_models) == 1:
            return available_models[0]
        
        if self.strategy == RoutingStrategy.FASTEST:
            return self._select_fastest(available_models)
        elif self.strategy == RoutingStrategy.MOST_CAPABLE:
            return self._select_most_capable(available_models)
        elif self.strategy == RoutingStrategy.BALANCED:
            return self._select_balanced(available_models)
        elif self.strategy == RoutingStrategy.COST_OPTIMIZED:
            return self._select_cost_optimized(available_models, context_tokens)
        elif self.strategy == RoutingStrategy.ROUND_ROBIN:
            return self._select_round_robin(available_models)
        elif self.strategy == RoutingStrategy.CUSTOM:
            if not self.custom_router:
                return available_models[0]
            return self.custom_router(available_models, task_description)
        else:
            return available_models[0]
    
    def _select_fastest(self, models: List[str]) -> str:
        """Select fastest/cheapest model."""
        if not self.provider_manager:
            return models[0]
        
        fastest = None
        min_cost = float('inf')
        
        for model_id in models:
            config = self.provider_manager.get_model(model_id)
            if not config:
                continue
            
            total_cost = config.cost_per_1k_input + config.cost_per_1k_output
            if total_cost < min_cost:
                min_cost = total_cost
                fastest = model_id
        
        return fastest or models[0]
    
    def _select_most_capable(self, models: List[str]) -> str:
        """Select most capable model."""
        if not self.provider_manager:
            return models[0]
        
        tier_priority = {
            "expert": 4,
            "capable": 3,
            "balanced": 2,
            "fast": 1
        }
        
        best_model = models[0]
        best_score = 0
        
        for model_id in models:
            config = self.provider_manager.get_model(model_id)
            if not config:
                continue
            
            score = tier_priority.get(config.tier.value, 0)
            if score > best_score:
                best_score = score
                best_model = model_id
        
        return best_model
    
    def _select_balanced(self, models: List[str]) -> str:
        """Select balanced model (cost vs capability)."""
        if not self.provider_manager:
            return models[0]
        
        # Prefer balanced tier
        for model_id in models:
            config = self.provider_manager.get_model(model_id)
            if config and config.tier.value == "balanced":
                return model_id
        
        # Fallback to capable if available
        for model_id in models:
            config = self.provider_manager.get_model(model_id)
            if config and config.tier.value == "capable":
                return model_id
        
        return models[0]
    
    def _select_cost_optimized(self, models: List[str], context_tokens: int) -> str:
        """Select most cost-effective model."""
        if not self.provider_manager:
            return models[0]
        
        best_model = models[0]
        min_cost = float('inf')
        
        for model_id in models:
            config = self.provider_manager.get_model(model_id)
            if not config:
                continue
            
            # Check if model has enough context window
            if config.context_window < context_tokens:
                continue
            
            # Estimate cost for this input
            cost = (context_tokens * config.cost_per_1k_input) / 1000
            
            if cost < min_cost:
                min_cost = cost
                best_model = model_id
        
        return best_model
    
    def _select_round_robin(self, models: List[str]) -> str:
        """Select model using round-robin."""
        model = models[self.round_robin_index % len(models)]
        self.round_robin_index += 1
        return model
    
    def record_usage(self, model_id: str, tokens_used: int = 0, 
                    cost: float = 0.0, error: bool = False,
                    latency_ms: float = 0.0) -> None:
        """Record model usage metrics.
        
        Args:
            model_id: Model used
            tokens_used: Tokens consumed
            cost: Cost incurred
            error: Whether request failed
            latency_ms: Request latency
        """
        if model_id not in self.usage_metrics:
            self.usage_metrics[model_id] = ModelUsageMetrics(model_id=model_id)
        
        metrics = self.usage_metrics[model_id]
        metrics.tokens_used += tokens_used
        metrics.cost += cost
        metrics.request_count += 1
        metrics.latency_ms = latency_ms
        
        if error:
            metrics.error_count += 1
            metrics.success_rate = 1.0 - (metrics.error_count / metrics.request_count)
        else:
            metrics.success_rate = 1.0 - (metrics.error_count / metrics.request_count)
    
    def get_metrics(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Get usage metrics.
        
        Args:
            model_id: Specific model or None for all
        
        Returns:
            Metrics dictionary
        """
        if model_id:
            metric = self.usage_metrics.get(model_id)
            return metric.to_dict() if metric else {}
        
        return {
            mid: metrics.to_dict()
            for mid, metrics in self.usage_metrics.items()
        }
    
    def get_total_cost(self) -> float:
        """Get total cost across all models."""
        return sum(m.cost for m in self.usage_metrics.values())
    
    def set_fallback_config(self, config: FallbackConfig) -> None:
        """Set fallback configuration.
        
        Args:
            config: Fallback configuration
        """
        self.fallback_config = config
    
    def get_fallback_model(self, failed_model: str, 
                          available_models: List[str]) -> Optional[str]:
        """Get fallback model after failure.
        
        Args:
            failed_model: Model that failed
            available_models: Other available models
        
        Returns:
            Fallback model or None
        """
        if not self.fallback_config.enabled:
            return None
        
        # Try configured fallback models first
        for fallback in self.fallback_config.fallback_models:
            if fallback in available_models and fallback != failed_model:
                return fallback
        
        # Try to find a different model
        for model in available_models:
            if model != failed_model:
                return model
        
        return None
    
    def set_custom_router(self, router_fn: Callable[[List[str], Optional[str]], str]) -> None:
        """Set custom routing function.
        
        Args:
            router_fn: Function that takes (models, task) and returns model_id
        """
        self.custom_router = router_fn
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "strategy": self.strategy.value,
            "usage_metrics": self.get_metrics(),
            "total_cost": self.get_total_cost(),
            "fallback_config": self.fallback_config.to_dict()
        }


class CostTracker:
    """Tracks costs across LLM calls."""
    
    def __init__(self):
        """Initialize cost tracker."""
        self.total_cost: float = 0.0
        self.total_tokens: int = 0
        self.per_model_cost: Dict[str, float] = {}
        self.per_model_tokens: Dict[str, int] = {}
        self.call_history: List[Dict[str, Any]] = []
    
    def track_call(self, model_id: str, input_tokens: int, output_tokens: int,
                  cost_per_1k_input: float, cost_per_1k_output: float,
                  metadata: Optional[Dict[str, Any]] = None) -> float:
        """Track a model call.
        
        Args:
            model_id: Model used
            input_tokens: Input tokens
            output_tokens: Output tokens
            cost_per_1k_input: Cost per 1K input tokens
            cost_per_1k_output: Cost per 1K output tokens
            metadata: Additional metadata
        
        Returns:
            Cost of this call
        """
        total_tokens = input_tokens + output_tokens
        
        cost = (input_tokens * cost_per_1k_input / 1000) + \
               (output_tokens * cost_per_1k_output / 1000)
        
        self.total_cost += cost
        self.total_tokens += total_tokens
        
        if model_id not in self.per_model_cost:
            self.per_model_cost[model_id] = 0.0
            self.per_model_tokens[model_id] = 0
        
        self.per_model_cost[model_id] += cost
        self.per_model_tokens[model_id] += total_tokens
        
        self.call_history.append({
            "model_id": model_id,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": cost,
            "timestamp": time.time(),
            "metadata": metadata or {}
        })
        
        return cost
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary."""
        return {
            "total_cost": self.total_cost,
            "total_tokens": self.total_tokens,
            "per_model_cost": self.per_model_cost,
            "per_model_tokens": self.per_model_tokens,
            "call_count": len(self.call_history),
            "average_cost_per_call": self.total_cost / len(self.call_history) if self.call_history else 0.0
        }
    
    def get_cost_by_model(self, model_id: str) -> Dict[str, Any]:
        """Get cost for specific model."""
        return {
            "model_id": model_id,
            "cost": self.per_model_cost.get(model_id, 0.0),
            "tokens": self.per_model_tokens.get(model_id, 0)
        }
    
    def reset(self) -> None:
        """Reset all tracking."""
        self.total_cost = 0.0
        self.total_tokens = 0
        self.per_model_cost = {}
        self.per_model_tokens = {}
        self.call_history = []
