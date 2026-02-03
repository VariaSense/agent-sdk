"""
Model Routing: Select best model by cost/latency and implement fallback chains.

Routes requests to appropriate LLM providers based on cost, latency, availability,
and other criteria. Implements fallback chains for resilience.
"""

from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from abc import ABC, abstractmethod


class ModelMetric(str, Enum):
    """Metrics for model selection."""
    COST = "cost"
    LATENCY = "latency"
    QUALITY = "quality"
    THROUGHPUT = "throughput"
    AVAILABILITY = "availability"


class SelectionStrategy(str, Enum):
    """Strategies for selecting between models."""
    LOWEST_COST = "lowest_cost"
    FASTEST = "fastest"
    HIGHEST_QUALITY = "highest_quality"
    BALANCED = "balanced"
    WEIGHTED = "weighted"
    ROUND_ROBIN = "round_robin"


@dataclass
class ModelMetrics:
    """Metrics for a specific model."""
    model_id: str
    cost_per_1k_tokens: float
    average_latency_ms: float
    quality_score: float = 0.8  # 0-1
    throughput_rps: float = 100.0  # requests per second
    availability: float = 0.99  # 0-1
    error_rate: float = 0.01  # 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_composite_score(
        self,
        weights: Dict[str, float],
    ) -> float:
        """
        Calculate weighted composite score.

        Args:
            weights: Dict of metric weights (cost, latency, quality, etc.)

        Returns:
            Weighted score (lower is better for cost/latency, higher for quality)
        """
        score = 0.0

        if "cost" in weights and weights["cost"] > 0:
            cost_normalized = min(self.cost_per_1k_tokens / 100, 1.0)
            score += cost_normalized * weights["cost"]

        if "latency" in weights and weights["latency"] > 0:
            latency_normalized = min(self.average_latency_ms / 5000, 1.0)
            score += latency_normalized * weights["latency"]

        if "quality" in weights and weights["quality"] > 0:
            quality_inverted = 1.0 - self.quality_score
            score += quality_inverted * weights["quality"]

        if "availability" in weights and weights["availability"] > 0:
            availability_inverted = 1.0 - self.availability
            score += availability_inverted * weights["availability"]

        return score


class ModelSelector:
    """Selects optimal model based on metrics and strategy."""

    def __init__(self, strategy: SelectionStrategy = SelectionStrategy.BALANCED):
        """
        Initialize model selector.

        Args:
            strategy: Selection strategy to use
        """
        self.strategy = strategy
        self.models: Dict[str, ModelMetrics] = {}
        self.selection_history: List[str] = []
        self.round_robin_index = 0

    def register_model(self, metrics: ModelMetrics) -> None:
        """Register a model with its metrics."""
        self.models[metrics.model_id] = metrics

    def register_models(self, metrics_list: List[ModelMetrics]) -> None:
        """Register multiple models."""
        for metrics in metrics_list:
            self.register_model(metrics)

    def select_model(
        self,
        available_models: Optional[List[str]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Select best model based on strategy.

        Args:
            available_models: List of available model IDs (defaults to all registered)
            constraints: Optional constraints (min_quality, max_cost, max_latency, etc.)

        Returns:
            Selected model ID or None if no suitable model
        """
        if not self.models:
            return None

        # Filter to available models
        candidates = {
            model_id: self.models[model_id]
            for model_id in (available_models or self.models.keys())
            if model_id in self.models
        }

        if not candidates:
            return None

        # Apply constraints
        if constraints:
            candidates = self._apply_constraints(candidates, constraints)

        if not candidates:
            return None

        # Select based on strategy
        selected = self._select_by_strategy(candidates)

        self.selection_history.append(selected)
        return selected

    def select_multiple(
        self,
        count: int,
        available_models: Optional[List[str]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Select multiple models in priority order.

        Args:
            count: Number of models to select
            available_models: Available models
            constraints: Optional constraints

        Returns:
            List of selected model IDs
        """
        selected = []
        remaining = dict(self.models)

        for _ in range(count):
            if not remaining:
                break

            # Filter to available
            candidates = {
                model_id: metrics
                for model_id, metrics in remaining.items()
                if model_id in (available_models or remaining.keys())
            }

            if not candidates:
                break

            # Apply constraints
            if constraints:
                candidates = self._apply_constraints(candidates, constraints)

            if not candidates:
                break

            # Select best
            best = self._select_by_strategy(candidates)
            selected.append(best)
            del remaining[best]

        return selected

    def update_metrics(
        self,
        model_id: str,
        metrics: ModelMetrics,
    ) -> None:
        """Update metrics for a model after observation."""
        if model_id in self.models:
            self.models[model_id] = metrics

    def get_model_metrics(self, model_id: str) -> Optional[ModelMetrics]:
        """Get metrics for a model."""
        return self.models.get(model_id)

    def get_all_metrics(self) -> Dict[str, ModelMetrics]:
        """Get all model metrics."""
        return self.models.copy()

    def _apply_constraints(
        self,
        candidates: Dict[str, ModelMetrics],
        constraints: Dict[str, Any],
    ) -> Dict[str, ModelMetrics]:
        """Filter candidates by constraints."""
        filtered = {}

        for model_id, metrics in candidates.items():
            passes = True

            if "min_quality" in constraints:
                if metrics.quality_score < constraints["min_quality"]:
                    passes = False

            if "max_cost" in constraints:
                if metrics.cost_per_1k_tokens > constraints["max_cost"]:
                    passes = False

            if "max_latency" in constraints:
                if metrics.average_latency_ms > constraints["max_latency"]:
                    passes = False

            if "min_availability" in constraints:
                if metrics.availability < constraints["min_availability"]:
                    passes = False

            if "max_error_rate" in constraints:
                if metrics.error_rate > constraints["max_error_rate"]:
                    passes = False

            if passes:
                filtered[model_id] = metrics

        return filtered

    def _select_by_strategy(self, candidates: Dict[str, ModelMetrics]) -> str:
        """Select model based on configured strategy."""
        if self.strategy == SelectionStrategy.LOWEST_COST:
            return min(
                candidates.items(),
                key=lambda x: x[1].cost_per_1k_tokens,
            )[0]

        elif self.strategy == SelectionStrategy.FASTEST:
            return min(
                candidates.items(),
                key=lambda x: x[1].average_latency_ms,
            )[0]

        elif self.strategy == SelectionStrategy.HIGHEST_QUALITY:
            return max(
                candidates.items(),
                key=lambda x: x[1].quality_score,
            )[0]

        elif self.strategy == SelectionStrategy.BALANCED:
            weights = {
                "cost": 0.33,
                "latency": 0.33,
                "quality": 0.34,
            }
            return self._select_by_weighted(candidates, weights)

        elif self.strategy == SelectionStrategy.WEIGHTED:
            weights = {
                "cost": 0.2,
                "latency": 0.3,
                "quality": 0.5,
            }
            return self._select_by_weighted(candidates, weights)

        elif self.strategy == SelectionStrategy.ROUND_ROBIN:
            model_ids = list(candidates.keys())
            selected = model_ids[self.round_robin_index % len(model_ids)]
            self.round_robin_index += 1
            return selected

        # Default to balanced
        return list(candidates.keys())[0]

    def _select_by_weighted(
        self,
        candidates: Dict[str, ModelMetrics],
        weights: Dict[str, float],
    ) -> str:
        """Select model with lowest weighted score."""
        scores = {
            model_id: metrics.get_composite_score(weights)
            for model_id, metrics in candidates.items()
        }
        return min(scores.items(), key=lambda x: x[1])[0]

    def get_selection_stats(self) -> Dict[str, Any]:
        """Get selection history statistics."""
        if not self.selection_history:
            return {}

        total_selections = len(self.selection_history)
        model_counts = {}
        for model_id in self.selection_history:
            model_counts[model_id] = model_counts.get(model_id, 0) + 1

        return {
            "total_selections": total_selections,
            "model_selection_counts": model_counts,
            "most_selected": max(model_counts.items(), key=lambda x: x[1])[0],
            "selection_distribution": {
                model_id: count / total_selections
                for model_id, count in model_counts.items()
            },
        }


class FallbackChain:
    """Manages fallback chains for model selection."""

    def __init__(self, primary: str, fallbacks: List[str]):
        """
        Initialize fallback chain.

        Args:
            primary: Primary model ID
            fallbacks: List of fallback model IDs in order
        """
        self.primary = primary
        self.fallbacks = fallbacks
        self.failure_counts: Dict[str, int] = {primary: 0}
        for fb in fallbacks:
            self.failure_counts[fb] = 0

    def get_next_available(
        self,
        available_models: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Get next available model in chain.

        Args:
            available_models: List of currently available models

        Returns:
            Next available model or None
        """
        available_set = set(available_models or [])

        if self.primary in available_set:
            return self.primary

        for fallback in self.fallbacks:
            if fallback in available_set:
                return fallback

        return None

    def record_failure(self, model_id: str) -> None:
        """Record a failure for a model."""
        if model_id in self.failure_counts:
            self.failure_counts[model_id] += 1

    def record_success(self, model_id: str) -> None:
        """Record a success for a model."""
        if model_id in self.failure_counts:
            self.failure_counts[model_id] = 0

    def get_failure_stats(self) -> Dict[str, int]:
        """Get failure counts for all models."""
        return self.failure_counts.copy()

    def reset_failures(self) -> None:
        """Reset all failure counts."""
        for model_id in self.failure_counts:
            self.failure_counts[model_id] = 0


class ModelRouter:
    """Routes requests to optimal model with fallback support."""

    def __init__(self):
        self.selectors: Dict[str, ModelSelector] = {}
        self.chains: Dict[str, FallbackChain] = {}
        self.available_models: Dict[str, bool] = {}

    def create_chain(
        self,
        chain_name: str,
        primary: str,
        fallbacks: List[str],
    ) -> None:
        """Create a fallback chain."""
        self.chains[chain_name] = FallbackChain(primary, fallbacks)

    def register_selector(
        self,
        selector_id: str,
        selector: ModelSelector,
    ) -> None:
        """Register a model selector."""
        self.selectors[selector_id] = selector

    def set_model_availability(self, model_id: str, available: bool) -> None:
        """Set model availability."""
        self.available_models[model_id] = available

    def get_available_models(self) -> List[str]:
        """Get list of available models."""
        return [
            model_id
            for model_id, available in self.available_models.items()
            if available
        ]

    def route_with_fallback(
        self,
        chain_name: str,
    ) -> Optional[str]:
        """
        Route request using fallback chain.

        Args:
            chain_name: Name of fallback chain

        Returns:
            Selected model ID or None
        """
        if chain_name not in self.chains:
            return None

        chain = self.chains[chain_name]
        available = self.get_available_models()
        return chain.get_next_available(available)

    def route_with_selector(
        self,
        selector_id: str,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Route request using model selector.

        Args:
            selector_id: ID of registered selector
            constraints: Optional constraints

        Returns:
            Selected model ID or None
        """
        if selector_id not in self.selectors:
            return None

        selector = self.selectors[selector_id]
        available = self.get_available_models()
        return selector.select_model(available, constraints)

    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        return {
            "available_models": self.get_available_models(),
            "chains": len(self.chains),
            "selectors": len(self.selectors),
        }
