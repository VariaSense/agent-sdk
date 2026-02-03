"""Tests for model router and cost tracking."""

import pytest
from agent_sdk.llm.router import (
    RoutingStrategy, ModelUsageMetrics, FallbackConfig,
    ModelRouter, CostTracker
)
from agent_sdk.llm.provider import ModelConfig, ProviderType, ModelTier, ProviderManager


class TestModelUsageMetrics:
    """Tests for ModelUsageMetrics."""
    
    def test_creation(self):
        """Test metrics creation."""
        metrics = ModelUsageMetrics(
            model_id="gpt-4",
            tokens_used=1000,
            cost=0.03
        )
        
        assert metrics.model_id == "gpt-4"
        assert metrics.tokens_used == 1000
        assert metrics.cost == 0.03
    
    def test_to_dict(self):
        """Test serialization."""
        metrics = ModelUsageMetrics(
            model_id="gpt-4",
            tokens_used=100,
            request_count=5
        )
        
        d = metrics.to_dict()
        
        assert d["model_id"] == "gpt-4"
        assert d["tokens_used"] == 100
        assert d["request_count"] == 5


class TestFallbackConfig:
    """Tests for FallbackConfig."""
    
    def test_creation(self):
        """Test fallback config creation."""
        config = FallbackConfig(
            enabled=True,
            max_retries=3,
            fallback_models=["gpt-3.5-turbo", "claude-3-haiku"]
        )
        
        assert config.enabled is True
        assert config.max_retries == 3
        assert len(config.fallback_models) == 2
    
    def test_to_dict(self):
        """Test serialization."""
        config = FallbackConfig(
            enabled=True,
            on_rate_limit=True,
            on_timeout=True
        )
        
        d = config.to_dict()
        
        assert d["enabled"] is True
        assert d["on_rate_limit"] is True


class TestModelRouter:
    """Tests for ModelRouter."""
    
    def test_initialization(self):
        """Test router initialization."""
        router = ModelRouter(strategy=RoutingStrategy.BALANCED)
        
        assert router.strategy == RoutingStrategy.BALANCED
    
    def test_select_single_model(self):
        """Test with single model (no routing needed)."""
        router = ModelRouter()
        
        selected = router.select_model(["gpt-4"])
        
        assert selected == "gpt-4"
    
    def test_select_model_fastest_strategy(self):
        """Test fastest strategy."""
        manager = ProviderManager()
        manager.register_model(ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI,
            tier=ModelTier.EXPERT,
            cost_per_1k_input=0.03,
            cost_per_1k_output=0.06
        ))
        manager.register_model(ModelConfig(
            model_id="gpt-3.5-turbo",
            provider=ProviderType.OPENAI,
            tier=ModelTier.FAST,
            cost_per_1k_input=0.0005,
            cost_per_1k_output=0.0015
        ))
        
        router = ModelRouter(strategy=RoutingStrategy.FASTEST, provider_manager=manager)
        
        selected = router.select_model(["gpt-4", "gpt-3.5-turbo"])
        
        assert selected == "gpt-3.5-turbo"
    
    def test_select_model_most_capable_strategy(self):
        """Test most capable strategy."""
        manager = ProviderManager()
        manager.register_model(ModelConfig(
            model_id="gpt-3.5-turbo",
            provider=ProviderType.OPENAI,
            tier=ModelTier.FAST
        ))
        manager.register_model(ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI,
            tier=ModelTier.EXPERT
        ))
        
        router = ModelRouter(strategy=RoutingStrategy.MOST_CAPABLE, provider_manager=manager)
        
        selected = router.select_model(["gpt-3.5-turbo", "gpt-4"])
        
        assert selected == "gpt-4"
    
    def test_select_model_balanced_strategy(self):
        """Test balanced strategy."""
        manager = ProviderManager()
        manager.register_model(ModelConfig(
            model_id="gpt-3.5-turbo",
            provider=ProviderType.OPENAI,
            tier=ModelTier.FAST
        ))
        manager.register_model(ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI,
            tier=ModelTier.BALANCED
        ))
        manager.register_model(ModelConfig(
            model_id="gpt-4-turbo",
            provider=ProviderType.OPENAI,
            tier=ModelTier.CAPABLE
        ))
        
        router = ModelRouter(strategy=RoutingStrategy.BALANCED, provider_manager=manager)
        
        selected = router.select_model(["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"])
        
        assert selected == "gpt-4"
    
    def test_select_model_cost_optimized_strategy(self):
        """Test cost optimized strategy."""
        manager = ProviderManager()
        manager.register_model(ModelConfig(
            model_id="small",
            provider=ProviderType.OPENAI,
            context_window=2048,
            cost_per_1k_input=0.001
        ))
        manager.register_model(ModelConfig(
            model_id="large",
            provider=ProviderType.OPENAI,
            context_window=128000,
            cost_per_1k_input=0.01
        ))
        
        router = ModelRouter(strategy=RoutingStrategy.COST_OPTIMIZED, provider_manager=manager)
        
        selected = router.select_model(["small", "large"], context_tokens=1000)
        
        # Should choose smaller context window for cost
        assert selected == "small"
    
    def test_select_model_round_robin_strategy(self):
        """Test round robin strategy."""
        router = ModelRouter(strategy=RoutingStrategy.ROUND_ROBIN)
        
        selected1 = router.select_model(["gpt-4", "gpt-3.5-turbo"])
        selected2 = router.select_model(["gpt-4", "gpt-3.5-turbo"])
        selected3 = router.select_model(["gpt-4", "gpt-3.5-turbo"])
        
        # Should alternate
        assert selected1 == "gpt-4"
        assert selected2 == "gpt-3.5-turbo"
        assert selected3 == "gpt-4"
    
    def test_record_usage(self):
        """Test recording usage metrics."""
        router = ModelRouter()
        
        router.record_usage("gpt-4", tokens_used=1000, cost=0.03)
        router.record_usage("gpt-4", tokens_used=500, cost=0.015)
        
        metrics = router.get_metrics("gpt-4")
        
        assert metrics["tokens_used"] == 1500
        assert metrics["cost"] == 0.045
        assert metrics["request_count"] == 2
    
    def test_record_usage_with_error(self):
        """Test recording usage with error."""
        router = ModelRouter()
        
        router.record_usage("gpt-4", tokens_used=100, error=False)
        router.record_usage("gpt-4", tokens_used=100, error=True)
        
        metrics = router.get_metrics("gpt-4")
        
        assert metrics["error_count"] == 1
        assert metrics["success_rate"] == 0.5
    
    def test_get_total_cost(self):
        """Test getting total cost."""
        router = ModelRouter()
        
        router.record_usage("gpt-4", cost=0.03)
        router.record_usage("gpt-3.5-turbo", cost=0.001)
        
        total = router.get_total_cost()
        
        assert total == 0.031
    
    def test_set_fallback_config(self):
        """Test setting fallback config."""
        router = ModelRouter()
        config = FallbackConfig(
            enabled=True,
            fallback_models=["gpt-3.5-turbo"]
        )
        
        router.set_fallback_config(config)
        
        assert router.fallback_config.enabled is True
        assert "gpt-3.5-turbo" in router.fallback_config.fallback_models
    
    def test_get_fallback_model(self):
        """Test getting fallback model."""
        router = ModelRouter()
        config = FallbackConfig(
            enabled=True,
            fallback_models=["gpt-3.5-turbo", "claude-3-haiku"]
        )
        router.set_fallback_config(config)
        
        fallback = router.get_fallback_model(
            "gpt-4",
            ["gpt-3.5-turbo", "claude-3-haiku", "gpt-4"]
        )
        
        assert fallback == "gpt-3.5-turbo"
    
    def test_get_fallback_model_disabled(self):
        """Test fallback with disabled config."""
        router = ModelRouter()
        config = FallbackConfig(enabled=False)
        router.set_fallback_config(config)
        
        fallback = router.get_fallback_model("gpt-4", ["gpt-3.5-turbo"])
        
        assert fallback is None
    
    def test_custom_router_function(self):
        """Test custom routing function."""
        router = ModelRouter(strategy=RoutingStrategy.CUSTOM)
        
        def custom_fn(models, task):
            # Always pick first model
            return models[0]
        
        router.set_custom_router(custom_fn)
        
        selected = router.select_model(["gpt-3.5-turbo", "gpt-4"])
        
        assert selected == "gpt-3.5-turbo"


class TestCostTracker:
    """Tests for CostTracker."""
    
    def test_initialization(self):
        """Test cost tracker creation."""
        tracker = CostTracker()
        
        assert tracker.total_cost == 0.0
        assert tracker.total_tokens == 0
    
    def test_track_call(self):
        """Test tracking a call."""
        tracker = CostTracker()
        
        cost = tracker.track_call(
            model_id="gpt-4",
            input_tokens=1000,
            output_tokens=500,
            cost_per_1k_input=0.03,
            cost_per_1k_output=0.06
        )
        
        assert cost > 0
        assert tracker.total_tokens == 1500
        assert tracker.total_cost > 0
    
    def test_track_multiple_calls(self):
        """Test tracking multiple calls."""
        tracker = CostTracker()
        
        tracker.track_call("gpt-4", 1000, 500, 0.03, 0.06)
        tracker.track_call("gpt-3.5-turbo", 2000, 1000, 0.0005, 0.0015)
        
        summary = tracker.get_cost_summary()
        
        assert len(summary["per_model_cost"]) == 2
        assert summary["call_count"] == 2
    
    def test_get_cost_summary(self):
        """Test cost summary."""
        tracker = CostTracker()
        tracker.track_call("gpt-4", 1000, 500, 0.03, 0.06)
        
        summary = tracker.get_cost_summary()
        
        assert "total_cost" in summary
        assert "total_tokens" in summary
        assert "per_model_cost" in summary
        assert "call_count" in summary
    
    def test_get_cost_by_model(self):
        """Test cost per model."""
        tracker = CostTracker()
        tracker.track_call("gpt-4", 1000, 500, 0.03, 0.06)
        tracker.track_call("gpt-3.5-turbo", 2000, 1000, 0.0005, 0.0015)
        
        gpt4_cost = tracker.get_cost_by_model("gpt-4")
        
        assert gpt4_cost["model_id"] == "gpt-4"
        assert gpt4_cost["tokens"] == 1500
        assert gpt4_cost["cost"] > 0
    
    def test_reset_tracking(self):
        """Test resetting tracker."""
        tracker = CostTracker()
        tracker.track_call("gpt-4", 1000, 500, 0.03, 0.06)
        
        tracker.reset()
        
        assert tracker.total_cost == 0.0
        assert tracker.total_tokens == 0
        assert len(tracker.call_history) == 0


class TestRoutingStrategyEnum:
    """Tests for RoutingStrategy enum."""
    
    def test_strategy_values(self):
        """Test routing strategy values."""
        assert RoutingStrategy.FASTEST.value == "fastest"
        assert RoutingStrategy.MOST_CAPABLE.value == "most_capable"
        assert RoutingStrategy.BALANCED.value == "balanced"
        assert RoutingStrategy.COST_OPTIMIZED.value == "cost_optimized"
        assert RoutingStrategy.ROUND_ROBIN.value == "round_robin"
        assert RoutingStrategy.CUSTOM.value == "custom"
