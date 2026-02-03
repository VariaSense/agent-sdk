"""
Tests for cost tracking module.
"""

import pytest
from datetime import datetime, timedelta
from agent_sdk.observability.cost_tracker import (
    CostTracker,
    ModelPricing,
    TokenUsage,
    OperationCost,
    CostSummary,
    create_cost_tracker,
    OPENAI_PRICING,
    ANTHROPIC_PRICING
)


class TestModelPricing:
    """Test ModelPricing class."""
    
    def test_create_pricing(self):
        """Test creating pricing model."""
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06,
            name="GPT-4"
        )
        assert pricing.model_id == "gpt-4"
        assert pricing.input_price_per_1k == 0.03
        assert pricing.output_price_per_1k == 0.06
    
    def test_calculate_input_cost(self):
        """Test input cost calculation."""
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06
        )
        cost = pricing.calculate_input_cost(1000)
        assert cost == pytest.approx(0.03)
    
    def test_calculate_output_cost(self):
        """Test output cost calculation."""
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06
        )
        cost = pricing.calculate_output_cost(1000)
        assert cost == pytest.approx(0.06)
    
    def test_calculate_total_cost(self):
        """Test total cost calculation."""
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06
        )
        cost = pricing.calculate_total_cost(1000, 2000)
        expected = 0.03 + 0.12
        assert cost == pytest.approx(expected)
    
    def test_pricing_to_dict(self):
        """Test pricing serialization."""
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06,
            name="GPT-4"
        )
        data = pricing.to_dict()
        assert data["model_id"] == "gpt-4"
        assert data["name"] == "GPT-4"


class TestTokenUsage:
    """Test TokenUsage class."""
    
    def test_create_token_usage(self):
        """Test creating token usage."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
    
    def test_total_tokens(self):
        """Test total tokens calculation."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150
    
    def test_token_usage_to_dict(self):
        """Test token usage serialization."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        data = usage.to_dict()
        assert data["input_tokens"] == 100
        assert data["output_tokens"] == 50
        assert data["total_tokens"] == 150


class TestCostTracker:
    """Test CostTracker class."""
    
    def test_create_tracker(self):
        """Test creating cost tracker."""
        tracker = CostTracker()
        assert len(tracker.pricing_models) == 0
    
    def test_register_pricing(self):
        """Test registering pricing."""
        tracker = CostTracker()
        pricing = ModelPricing(
            model_id="gpt-4",
            input_price_per_1k=0.03,
            output_price_per_1k=0.06
        )
        tracker.register_pricing(pricing)
        assert "gpt-4" in tracker.pricing_models
    
    def test_register_multiple_pricing(self):
        """Test registering multiple pricing."""
        tracker = CostTracker()
        pricing_list = [
            ModelPricing(
                model_id="gpt-4",
                input_price_per_1k=0.03,
                output_price_per_1k=0.06
            ),
            ModelPricing(
                model_id="gpt-3.5-turbo",
                input_price_per_1k=0.0005,
                output_price_per_1k=0.0015
            )
        ]
        tracker.register_multiple_pricing(pricing_list)
        assert len(tracker.pricing_models) == 2
    
    def test_record_operation(self):
        """Test recording operation."""
        tracker = CostTracker(OPENAI_PRICING)
        op = tracker.record_operation(
            operation_id="op-1",
            operation_name="completion",
            model_id="gpt-4",
            input_tokens=100,
            output_tokens=50,
            metadata={"agent_id": "agent-1"}
        )
        assert op.cost > 0
        assert op.operation_id == "op-1"
    
    def test_record_operation_invalid_model(self):
        """Test recording operation with invalid model."""
        tracker = CostTracker()
        with pytest.raises(ValueError):
            tracker.record_operation(
                operation_id="op-1",
                operation_name="completion",
                model_id="invalid-model",
                input_tokens=100,
                output_tokens=50
            )
    
    def test_get_operation(self):
        """Test getting operation."""
        tracker = CostTracker(OPENAI_PRICING)
        tracker.record_operation(
            operation_id="op-1",
            operation_name="completion",
            model_id="gpt-4",
            input_tokens=100,
            output_tokens=50
        )
        op = tracker.get_operation("op-1")
        assert op is not None
        assert op.operation_id == "op-1"
    
    def test_get_agent_costs(self):
        """Test getting agent costs."""
        tracker = CostTracker(OPENAI_PRICING)
        
        # Record multiple operations for same agent
        for i in range(3):
            tracker.record_operation(
                operation_id=f"op-{i}",
                operation_name="completion",
                model_id="gpt-4",
                input_tokens=100,
                output_tokens=50,
                metadata={"agent_id": "agent-1"}
            )
        
        summary = tracker.get_agent_costs("agent-1")
        assert summary.operation_count == 3
        assert summary.total_cost > 0
    
    def test_get_model_costs(self):
        """Test getting model costs."""
        tracker = CostTracker(OPENAI_PRICING)
        
        # Record operations with different models
        tracker.record_operation(
            operation_id="op-1",
            operation_name="completion",
            model_id="gpt-4",
            input_tokens=100,
            output_tokens=50
        )
        tracker.record_operation(
            operation_id="op-2",
            operation_name="completion",
            model_id="gpt-3.5-turbo",
            input_tokens=100,
            output_tokens=50
        )
        
        summary = tracker.get_model_costs("gpt-4")
        assert summary.operation_count == 1
    
    def test_get_total_costs(self):
        """Test getting total costs."""
        tracker = CostTracker(OPENAI_PRICING)
        
        # Record multiple operations
        for i in range(5):
            tracker.record_operation(
                operation_id=f"op-{i}",
                operation_name="completion",
                model_id="gpt-4",
                input_tokens=100,
                output_tokens=50
            )
        
        summary = tracker.get_total_costs()
        assert summary.operation_count == 5
        assert summary.total_tokens == 5 * 150
    
    def test_cost_summary_statistics(self):
        """Test cost summary statistics."""
        tracker = CostTracker(OPENAI_PRICING)
        
        tracker.record_operation(
            operation_id="op-1",
            operation_name="completion",
            model_id="gpt-4",
            input_tokens=100,
            output_tokens=50
        )
        
        summary = tracker.get_total_costs()
        assert summary.average_cost_per_operation > 0
        assert summary.average_tokens_per_operation == 150
    
    def test_cost_summary_to_dict(self):
        """Test cost summary serialization."""
        tracker = CostTracker(OPENAI_PRICING)
        
        tracker.record_operation(
            operation_id="op-1",
            operation_name="completion",
            model_id="gpt-4",
            input_tokens=100,
            output_tokens=50
        )
        
        summary = tracker.get_total_costs()
        data = summary.to_dict()
        assert "total_cost" in data
        assert "total_tokens" in data
        assert "operation_count" in data
    
    def test_clear_operations(self):
        """Test clearing operations."""
        tracker = CostTracker(OPENAI_PRICING)
        
        tracker.record_operation(
            operation_id="op-1",
            operation_name="completion",
            model_id="gpt-4",
            input_tokens=100,
            output_tokens=50
        )
        
        assert len(tracker.operations) == 1
        tracker.clear_operations()
        assert len(tracker.operations) == 0


class TestCreateCostTracker:
    """Test cost tracker factory function."""
    
    def test_create_openai_tracker(self):
        """Test creating OpenAI tracker."""
        tracker = create_cost_tracker("openai")
        assert len(tracker.pricing_models) >= 2
        assert "gpt-4" in tracker.pricing_models
    
    def test_create_anthropic_tracker(self):
        """Test creating Anthropic tracker."""
        tracker = create_cost_tracker("anthropic")
        assert len(tracker.pricing_models) >= 1
        assert "claude-3-opus" in tracker.pricing_models
    
    def test_create_combined_tracker(self):
        """Test creating combined tracker."""
        tracker = create_cost_tracker("combined")
        assert len(tracker.pricing_models) >= 3


class TestCostTrackerIntegration:
    """Integration tests for cost tracker."""
    
    def test_track_conversation_costs(self):
        """Test tracking costs for a conversation."""
        tracker = create_cost_tracker("openai")
        
        # Simulate conversation with multiple turns
        conversation_id = "conv-1"
        
        for turn in range(3):
            tracker.record_operation(
                operation_id=f"{conversation_id}-turn-{turn}",
                operation_name="chat_completion",
                model_id="gpt-4",
                input_tokens=150 + turn * 50,  # Increasing context
                output_tokens=100,
                metadata={
                    "agent_id": "chatbot-1",
                    "conversation_id": conversation_id,
                    "turn": turn
                }
            )
        
        # Get conversation costs
        summary = tracker.get_agent_costs("chatbot-1")
        assert summary.operation_count == 3
        assert summary.total_input_tokens > 150
    
    def test_track_multi_model_costs(self):
        """Test tracking costs across multiple models."""
        tracker = create_cost_tracker("combined")
        
        # Use GPT-4
        tracker.record_operation(
            operation_id="op-1",
            operation_name="reasoning",
            model_id="gpt-4",
            input_tokens=500,
            output_tokens=200,
            metadata={"agent_id": "analyzer"}
        )
        
        # Use Claude
        tracker.record_operation(
            operation_id="op-2",
            operation_name="summarization",
            model_id="claude-3-opus",
            input_tokens=400,
            output_tokens=150,
            metadata={"agent_id": "analyzer"}
        )
        
        summary = tracker.get_agent_costs("analyzer")
        assert summary.operation_count == 2
        assert len(summary.cost_by_model) == 2
