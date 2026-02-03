"""
Tests for Model Routing.
"""

import pytest
from agent_sdk.core.model_routing import (
    ModelMetrics,
    ModelSelector,
    FallbackChain,
    ModelRouter,
    SelectionStrategy,
)


@pytest.fixture
def sample_models():
    """Create sample model metrics."""
    return [
        ModelMetrics(
            model_id="gpt-4",
            cost_per_1k_tokens=0.03,
            average_latency_ms=2000,
            quality_score=0.95,
            availability=0.99,
        ),
        ModelMetrics(
            model_id="gpt-3.5",
            cost_per_1k_tokens=0.002,
            average_latency_ms=500,
            quality_score=0.85,
            availability=0.99,
        ),
        ModelMetrics(
            model_id="claude",
            cost_per_1k_tokens=0.008,
            average_latency_ms=1500,
            quality_score=0.92,
            availability=0.98,
        ),
    ]


class TestModelMetrics:
    """Test ModelMetrics class."""

    def test_create_metrics(self):
        """Test creating model metrics."""
        metrics = ModelMetrics(
            model_id="gpt-4",
            cost_per_1k_tokens=0.03,
            average_latency_ms=2000,
            quality_score=0.95,
        )

        assert metrics.model_id == "gpt-4"
        assert metrics.cost_per_1k_tokens == 0.03
        assert metrics.average_latency_ms == 2000

    def test_get_composite_score(self):
        """Test composite score calculation."""
        metrics = ModelMetrics(
            model_id="model1",
            cost_per_1k_tokens=0.01,
            average_latency_ms=1000,
            quality_score=0.8,
        )

        score = metrics.get_composite_score({
            "cost": 0.33,
            "latency": 0.33,
            "quality": 0.34,
        })

        assert score >= 0
        assert isinstance(score, float)


class TestModelSelector:
    """Test ModelSelector class."""

    def test_create_selector(self):
        """Test creating selector."""
        selector = ModelSelector()
        assert selector.strategy == SelectionStrategy.BALANCED

    def test_create_selector_with_strategy(self):
        """Test creating selector with strategy."""
        selector = ModelSelector(SelectionStrategy.LOWEST_COST)
        assert selector.strategy == SelectionStrategy.LOWEST_COST

    def test_register_model(self, sample_models):
        """Test registering a model."""
        selector = ModelSelector()
        selector.register_model(sample_models[0])

        assert sample_models[0].model_id in selector.models

    def test_register_multiple_models(self, sample_models):
        """Test registering multiple models."""
        selector = ModelSelector()
        selector.register_models(sample_models)

        assert len(selector.models) == 3

    def test_select_model_lowest_cost(self, sample_models):
        """Test selecting lowest cost model."""
        selector = ModelSelector(SelectionStrategy.LOWEST_COST)
        selector.register_models(sample_models)

        selected = selector.select_model()
        assert selected == "gpt-3.5"  # Cheapest

    def test_select_model_fastest(self, sample_models):
        """Test selecting fastest model."""
        selector = ModelSelector(SelectionStrategy.FASTEST)
        selector.register_models(sample_models)

        selected = selector.select_model()
        assert selected == "gpt-3.5"  # Fastest

    def test_select_model_highest_quality(self, sample_models):
        """Test selecting highest quality model."""
        selector = ModelSelector(SelectionStrategy.HIGHEST_QUALITY)
        selector.register_models(sample_models)

        selected = selector.select_model()
        assert selected == "gpt-4"  # Best quality

    def test_select_model_balanced(self, sample_models):
        """Test balanced selection."""
        selector = ModelSelector(SelectionStrategy.BALANCED)
        selector.register_models(sample_models)

        selected = selector.select_model()
        assert selected is not None
        assert selected in [m.model_id for m in sample_models]

    def test_select_model_with_constraints(self, sample_models):
        """Test selection with constraints."""
        selector = ModelSelector(SelectionStrategy.LOWEST_COST)
        selector.register_models(sample_models)

        # Require quality >= 0.9
        selected = selector.select_model(
            constraints={"min_quality": 0.9}
        )

        assert selected in ["gpt-4", "claude"]

    def test_select_model_no_models(self):
        """Test selection with no models."""
        selector = ModelSelector()
        selected = selector.select_model()

        assert selected is None

    def test_select_multiple_models(self, sample_models):
        """Test selecting multiple models."""
        selector = ModelSelector()
        selector.register_models(sample_models)

        selected = selector.select_multiple(2)
        assert len(selected) == 2

    def test_update_metrics(self, sample_models):
        """Test updating metrics."""
        selector = ModelSelector()
        selector.register_model(sample_models[0])

        new_metrics = ModelMetrics(
            model_id="gpt-4",
            cost_per_1k_tokens=0.04,
            average_latency_ms=2500,
            quality_score=0.93,
        )

        selector.update_metrics("gpt-4", new_metrics)
        updated = selector.get_model_metrics("gpt-4")

        assert updated.cost_per_1k_tokens == 0.04

    def test_get_model_metrics(self, sample_models):
        """Test getting model metrics."""
        selector = ModelSelector()
        selector.register_model(sample_models[0])

        metrics = selector.get_model_metrics("gpt-4")
        assert metrics.model_id == "gpt-4"

    def test_get_all_metrics(self, sample_models):
        """Test getting all metrics."""
        selector = ModelSelector()
        selector.register_models(sample_models)

        all_metrics = selector.get_all_metrics()
        assert len(all_metrics) == 3

    def test_get_selection_stats(self, sample_models):
        """Test selection statistics."""
        selector = ModelSelector()
        selector.register_models(sample_models)

        selector.select_model()
        selector.select_model()

        stats = selector.get_selection_stats()
        assert "total_selections" in stats
        assert stats["total_selections"] == 2

    def test_round_robin_selection(self, sample_models):
        """Test round-robin selection."""
        selector = ModelSelector(SelectionStrategy.ROUND_ROBIN)
        selector.register_models(sample_models)

        selected1 = selector.select_model()
        selected2 = selector.select_model()
        selected3 = selector.select_model()

        # Should cycle through different models
        assert selected1 is not None
        assert selected2 is not None
        assert selected3 is not None


class TestFallbackChain:
    """Test FallbackChain class."""

    def test_create_chain(self):
        """Test creating chain."""
        chain = FallbackChain("primary", ["fb1", "fb2"])

        assert chain.primary == "primary"
        assert len(chain.fallbacks) == 2

    def test_get_next_primary(self):
        """Test getting primary model."""
        chain = FallbackChain("primary", ["fb1", "fb2"])

        next_model = chain.get_next_available(["primary", "fb1"])
        assert next_model == "primary"

    def test_get_next_fallback(self):
        """Test falling back to secondary."""
        chain = FallbackChain("primary", ["fb1", "fb2"])

        next_model = chain.get_next_available(["fb1", "fb2"])
        assert next_model == "fb1"

    def test_get_next_no_available(self):
        """Test when no models available."""
        chain = FallbackChain("primary", ["fb1"])

        next_model = chain.get_next_available(["other"])
        assert next_model is None

    def test_record_failure(self):
        """Test recording failure."""
        chain = FallbackChain("primary", ["fb1"])

        chain.record_failure("primary")
        assert chain.failure_counts["primary"] > 0

    def test_record_success(self):
        """Test recording success."""
        chain = FallbackChain("primary", ["fb1"])

        chain.record_failure("primary")
        chain.record_success("primary")

        assert chain.failure_counts["primary"] == 0

    def test_get_failure_stats(self):
        """Test getting failure stats."""
        chain = FallbackChain("primary", ["fb1"])

        chain.record_failure("primary")
        chain.record_failure("fb1")

        stats = chain.get_failure_stats()
        assert stats["primary"] > 0
        assert stats["fb1"] > 0

    def test_reset_failures(self):
        """Test resetting failures."""
        chain = FallbackChain("primary", ["fb1"])

        chain.record_failure("primary")
        assert chain.failure_counts["primary"] > 0

        chain.reset_failures()
        assert chain.failure_counts["primary"] == 0


class TestModelRouter:
    """Test ModelRouter class."""

    def test_create_router(self):
        """Test creating router."""
        router = ModelRouter()
        assert len(router.chains) == 0
        assert len(router.selectors) == 0

    def test_create_chain(self):
        """Test creating chain in router."""
        router = ModelRouter()
        router.create_chain("default", "primary", ["fb1", "fb2"])

        assert "default" in router.chains

    def test_set_model_availability(self):
        """Test setting availability."""
        router = ModelRouter()

        router.set_model_availability("gpt-4", True)
        router.set_model_availability("gpt-3.5", True)

        available = router.get_available_models()
        assert "gpt-4" in available

    def test_route_with_fallback(self):
        """Test routing with fallback chain."""
        router = ModelRouter()
        router.create_chain("main", "primary", ["secondary"])
        router.set_model_availability("primary", True)

        selected = router.route_with_fallback("main")
        assert selected == "primary"

    def test_route_with_fallback_unavailable_primary(self):
        """Test fallback when primary unavailable."""
        router = ModelRouter()
        router.create_chain("main", "primary", ["secondary"])
        router.set_model_availability("secondary", True)

        selected = router.route_with_fallback("main")
        assert selected == "secondary"

    def test_route_with_selector(self, sample_models):
        """Test routing with selector."""
        router = ModelRouter()

        selector = ModelSelector(SelectionStrategy.LOWEST_COST)
        selector.register_models(sample_models)
        router.register_selector("cost", selector)

        router.set_model_availability("gpt-3.5", True)
        router.set_model_availability("claude", True)

        selected = router.route_with_selector("cost")
        assert selected is not None

    def test_get_routing_stats(self):
        """Test routing statistics."""
        router = ModelRouter()

        router.create_chain("chain1", "primary", ["fb"])
        selector = ModelSelector()
        router.register_selector("selector1", selector)

        stats = router.get_routing_stats()
        assert stats["chains"] == 1
        assert stats["selectors"] == 1
