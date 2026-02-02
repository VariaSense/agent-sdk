"""Tests for multi-model support and routing."""

import pytest
from agent_sdk.llm.model_router import (
    ModelProvider,
    ModelConfig,
    ModelUsageStats,
    ModelRouter,
    CostOptimizedStrategy,
    PerformanceOptimizedStrategy,
    QualityOptimizedStrategy,
    AdaptiveStrategy,
    GPT_4,
    GPT_35_TURBO,
    CLAUDE_3_OPUS,
)


def test_model_config_creation():
    """Test creating a model config."""
    config = ModelConfig(
        name="test-model",
        provider=ModelProvider.OPENAI,
        max_tokens=2048,
        temperature=0.7,
        cost_per_1k_input=0.01,
        cost_per_1k_output=0.02,
    )
    
    assert config.name == "test-model"
    assert config.provider == ModelProvider.OPENAI
    assert config.max_tokens == 2048


def test_model_config_merge():
    """Test merging model configs."""
    config1 = ModelConfig(
        name="model1",
        provider=ModelProvider.OPENAI,
        temperature=0.7,
    )
    
    config2 = config1.merge({"temperature": 0.5, "max_tokens": 4096})
    
    assert config2.temperature == 0.5
    assert config2.max_tokens == 4096
    assert config2.name == config1.name


def test_model_usage_stats():
    """Test tracking model usage."""
    stats = ModelUsageStats(model_name="gpt-4")
    
    # Add some usage
    stats.add_usage(
        input_tokens=100,
        output_tokens=50,
        cost_per_1k_input=0.03,
        cost_per_1k_output=0.06,
        latency_ms=500,
    )
    
    assert stats.input_tokens == 100
    assert stats.output_tokens == 50
    assert stats.total_requests == 1
    assert stats.total_cost > 0


def test_model_usage_stats_failure():
    """Test recording failures."""
    stats = ModelUsageStats(model_name="gpt-3.5")
    
    stats.add_usage(100, 50, 0.001, 0.002, 100)
    stats.record_failure()
    stats.add_usage(100, 50, 0.001, 0.002, 100)
    
    assert stats.total_requests == 2
    assert stats.failed_requests == 1
    assert stats.success_rate() == 50.0


def test_model_usage_stats_calculations():
    """Test usage calculations."""
    stats = ModelUsageStats(model_name="claude")
    
    # Add multiple requests
    for _ in range(5):
        stats.add_usage(200, 100, 0.015, 0.075, 300)
    
    assert stats.input_tokens == 1000
    assert stats.output_tokens == 500
    assert stats.total_requests == 5
    assert stats.avg_input_tokens() == 200
    assert stats.avg_output_tokens() == 100


def test_cost_optimized_strategy():
    """Test cost-optimized model selection."""
    models = [
        ModelConfig("gpt-4", ModelProvider.OPENAI, cost_per_1k_input=0.03, cost_per_1k_output=0.06),
        ModelConfig("gpt-3.5", ModelProvider.OPENAI, cost_per_1k_input=0.0005, cost_per_1k_output=0.0015),
        ModelConfig("claude-opus", ModelProvider.ANTHROPIC, cost_per_1k_input=0.015, cost_per_1k_output=0.075),
    ]
    
    strategy = CostOptimizedStrategy()
    selection = strategy.select(models, {})
    
    # Should pick GPT-3.5 (cheapest)
    assert selection.primary_model.name == "gpt-3.5"
    assert "cheapest" in selection.reason.lower()


def test_performance_optimized_strategy():
    """Test performance-optimized selection."""
    models = [
        ModelConfig("slow-model", ModelProvider.OPENAI),
        ModelConfig("fast-model", ModelProvider.OPENAI),
    ]
    
    stats = {
        "slow-model": ModelUsageStats("slow-model"),
        "fast-model": ModelUsageStats("fast-model"),
    }
    
    # Simulate latencies
    stats["slow-model"].latency_ms = 1000
    stats["fast-model"].latency_ms = 100
    
    strategy = PerformanceOptimizedStrategy()
    selection = strategy.select(models, stats)
    
    assert selection.primary_model.name == "fast-model"


def test_quality_optimized_strategy():
    """Test quality-optimized selection."""
    models = [
        ModelConfig("gpt-4", ModelProvider.OPENAI),
        ModelConfig("gpt-3.5-turbo", ModelProvider.OPENAI),
        ModelConfig("claude-3-opus", ModelProvider.ANTHROPIC),
    ]
    
    strategy = QualityOptimizedStrategy()
    selection = strategy.select(models, {}, task_type="reasoning")
    
    # Should prefer gpt-4 for reasoning
    assert "gpt-4" in selection.primary_model.name.lower()


def test_adaptive_strategy():
    """Test adaptive selection strategy."""
    models = [
        ModelConfig("model-a", ModelProvider.OPENAI, cost_per_1k_input=0.01, cost_per_1k_output=0.02),
        ModelConfig("model-b", ModelProvider.OPENAI, cost_per_1k_input=0.02, cost_per_1k_output=0.04),
    ]
    
    stats = {
        "model-a": ModelUsageStats("model-a"),
        "model-b": ModelUsageStats("model-b"),
    }
    
    # Model A has good performance, Model B has issues
    stats["model-a"].latency_ms = 100
    stats["model-b"].latency_ms = 500
    stats["model-b"].record_failure()
    
    strategy = AdaptiveStrategy()
    selection = strategy.select(models, stats)
    
    # Should prefer model-a due to better performance and reliability
    assert selection.primary_model.name == "model-a"


def test_model_router_add_models():
    """Test adding models to router."""
    router = ModelRouter()
    
    router.add_model(GPT_4)
    router.add_model(GPT_35_TURBO)
    
    assert router.select_models().primary_model.name == "gpt-3.5-turbo"  # Cheapest


def test_model_router_record_usage():
    """Test recording usage in router."""
    router = ModelRouter()
    router.add_model(GPT_4)
    
    router.record_usage(
        model_name="gpt-4",
        input_tokens=100,
        output_tokens=50,
        latency_ms=500,
        success=True
    )
    
    stats = router.get_stats("gpt-4")
    assert stats["gpt-4"].total_requests == 1
    assert stats["gpt-4"].input_tokens == 100


def test_model_router_cost_tracking():
    """Test cost tracking in router."""
    router = ModelRouter()
    router.add_model(GPT_4)
    
    # Record a request
    router.record_usage(
        model_name="gpt-4",
        input_tokens=1000,
        output_tokens=500,
        success=True
    )
    
    total_cost = router.get_total_cost()
    assert total_cost > 0
    
    breakdown = router.get_cost_breakdown()
    assert "gpt-4" in breakdown
    assert breakdown["gpt-4"] > 0


def test_model_router_fallback():
    """Test fallback model selection."""
    router = ModelRouter()
    router.add_models([GPT_4, GPT_35_TURBO, CLAUDE_3_OPUS])
    
    selection = router.select_models()
    
    assert selection.primary_model is not None
    assert len(selection.fallback_models) > 0


def test_model_router_switch_strategy():
    """Test switching selection strategies."""
    router = ModelRouter()
    router.add_models([GPT_4, GPT_35_TURBO])
    
    # Cost optimized (default)
    selection1 = router.select_models()
    
    # Switch to quality
    router.switch_strategy(QualityOptimizedStrategy())
    selection2 = router.select_models()
    
    # May select different models based on strategy
    assert selection1.primary_model is not None
    assert selection2.primary_model is not None


def test_predefined_models():
    """Test predefined model configurations."""
    assert GPT_4.provider == ModelProvider.OPENAI
    assert GPT_35_TURBO.provider == ModelProvider.OPENAI
    assert CLAUDE_3_OPUS.provider == ModelProvider.ANTHROPIC
    
    # GPT-4 is more expensive
    assert GPT_4.cost_per_1k_input > GPT_35_TURBO.cost_per_1k_input


def test_model_selection_with_multiple_models():
    """Test selecting from multiple models."""
    router = ModelRouter()
    
    # Add different models
    router.add_models([
        GPT_4,
        GPT_35_TURBO,
        CLAUDE_3_OPUS,
    ])
    
    selection = router.select_models(task_type="reasoning")
    
    assert selection.primary_model is not None
    assert isinstance(selection.fallback_models, list)
    assert len(selection.fallback_models) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
