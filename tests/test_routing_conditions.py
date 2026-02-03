"""Tests for routing conditions."""

import pytest
from agent_sdk.routing.conditions import (
    TokenCountCondition,
    ConfidenceCondition,
    ToolAvailabilityCondition,
    ModelCapabilityCondition,
    CostCondition,
    ContextTypeCondition,
    CompoundCondition,
)


class MockContext:
    """Mock execution context for testing."""
    
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestTokenCountCondition:
    """Test TokenCountCondition."""
    
    def test_within_range_true(self):
        """Test token count within range."""
        condition = TokenCountCondition(max_tokens=100, min_tokens=0, comparison="within")
        context = MockContext(estimated_tokens=50)
        
        assert condition.evaluate(context) is True
    
    def test_within_range_false_above(self):
        """Test token count above range."""
        condition = TokenCountCondition(max_tokens=100, min_tokens=0, comparison="within")
        context = MockContext(estimated_tokens=150)
        
        assert condition.evaluate(context) is False
    
    def test_within_range_false_below(self):
        """Test token count below minimum."""
        condition = TokenCountCondition(max_tokens=100, min_tokens=10, comparison="within")
        context = MockContext(estimated_tokens=5)
        
        assert condition.evaluate(context) is False
    
    def test_above_comparison(self):
        """Test above comparison."""
        condition = TokenCountCondition(max_tokens=100, comparison="above")
        context = MockContext(estimated_tokens=150)
        
        assert condition.evaluate(context) is True
    
    def test_above_comparison_false(self):
        """Test above comparison when below."""
        condition = TokenCountCondition(max_tokens=100, comparison="above")
        context = MockContext(estimated_tokens=50)
        
        assert condition.evaluate(context) is False
    
    def test_below_comparison(self):
        """Test below comparison."""
        condition = TokenCountCondition(min_tokens=50, comparison="below")
        context = MockContext(estimated_tokens=30)
        
        assert condition.evaluate(context) is True
    
    def test_below_comparison_false(self):
        """Test below comparison when above."""
        condition = TokenCountCondition(min_tokens=50, comparison="below")
        context = MockContext(estimated_tokens=100)
        
        assert condition.evaluate(context) is False
    
    def test_missing_estimated_tokens(self):
        """Test with missing estimated_tokens attribute."""
        condition = TokenCountCondition(max_tokens=100)
        context = MockContext()  # No estimated_tokens
        
        assert condition.evaluate(context) is True  # Defaults to 0


class TestConfidenceCondition:
    """Test ConfidenceCondition."""
    
    def test_confidence_within_range_true(self):
        """Test confidence within range."""
        condition = ConfidenceCondition(min_confidence=0.5, max_confidence=0.9)
        context = MockContext(confidence_score=0.7)
        
        assert condition.evaluate(context) is True
    
    def test_confidence_above_range(self):
        """Test confidence above range."""
        condition = ConfidenceCondition(min_confidence=0.5, max_confidence=0.9)
        context = MockContext(confidence_score=0.95)
        
        assert condition.evaluate(context) is False
    
    def test_confidence_below_range(self):
        """Test confidence below range."""
        condition = ConfidenceCondition(min_confidence=0.5, max_confidence=0.9)
        context = MockContext(confidence_score=0.3)
        
        assert condition.evaluate(context) is False
    
    def test_confidence_boundary_min(self):
        """Test confidence at minimum boundary."""
        condition = ConfidenceCondition(min_confidence=0.5, max_confidence=0.9)
        context = MockContext(confidence_score=0.5)
        
        assert condition.evaluate(context) is True
    
    def test_confidence_boundary_max(self):
        """Test confidence at maximum boundary."""
        condition = ConfidenceCondition(min_confidence=0.5, max_confidence=0.9)
        context = MockContext(confidence_score=0.9)
        
        assert condition.evaluate(context) is True
    
    def test_confidence_clamping(self):
        """Test confidence value clamping."""
        condition = ConfidenceCondition(min_confidence=-0.5, max_confidence=1.5)
        
        assert condition.min_confidence == 0.0
        assert condition.max_confidence == 1.0
    
    def test_missing_confidence_score(self):
        """Test with missing confidence_score attribute."""
        condition = ConfidenceCondition(min_confidence=0.5)
        context = MockContext()  # No confidence_score
        
        # Defaults to 0.5 when missing, which is equal to min_confidence
        assert condition.evaluate(context) is True


class TestToolAvailabilityCondition:
    """Test ToolAvailabilityCondition."""
    
    def test_all_tools_available(self):
        """Test all required tools available."""
        condition = ToolAvailabilityCondition(
            required_tools=["search", "calculator"],
            require_all=True
        )
        context = MockContext(available_tools=["search", "calculator", "translator"])
        
        assert condition.evaluate(context) is True
    
    def test_not_all_tools_available(self):
        """Test not all required tools available."""
        condition = ToolAvailabilityCondition(
            required_tools=["search", "calculator"],
            require_all=True
        )
        context = MockContext(available_tools=["search"])
        
        assert condition.evaluate(context) is False
    
    def test_any_tool_available(self):
        """Test any required tool available."""
        condition = ToolAvailabilityCondition(
            required_tools=["search", "calculator"],
            require_all=False
        )
        context = MockContext(available_tools=["search"])
        
        assert condition.evaluate(context) is True
    
    def test_no_required_tools_available(self):
        """Test no required tools available."""
        condition = ToolAvailabilityCondition(
            required_tools=["search", "calculator"],
            require_all=False
        )
        context = MockContext(available_tools=["translator"])
        
        assert condition.evaluate(context) is False
    
    def test_empty_required_tools(self):
        """Test with empty required tools list."""
        condition = ToolAvailabilityCondition(required_tools=[])
        context = MockContext(available_tools=[])
        
        assert condition.evaluate(context) is True
    
    def test_missing_available_tools(self):
        """Test with missing available_tools attribute."""
        condition = ToolAvailabilityCondition(required_tools=["search"])
        context = MockContext()  # No available_tools
        
        assert condition.evaluate(context) is False


class TestModelCapabilityCondition:
    """Test ModelCapabilityCondition."""
    
    def test_capability_present_required(self):
        """Test required capability is present."""
        condition = ModelCapabilityCondition(capability="vision", required=True)
        context = MockContext(model_capabilities=["vision", "function_calling"])
        
        assert condition.evaluate(context) is True
    
    def test_capability_missing_required(self):
        """Test required capability is missing."""
        condition = ModelCapabilityCondition(capability="vision", required=True)
        context = MockContext(model_capabilities=["function_calling"])
        
        assert condition.evaluate(context) is False
    
    def test_capability_present_not_required(self):
        """Test capability present when not required."""
        condition = ModelCapabilityCondition(capability="vision", required=False)
        context = MockContext(model_capabilities=["vision"])
        
        assert condition.evaluate(context) is False
    
    def test_capability_missing_not_required(self):
        """Test capability missing when not required."""
        condition = ModelCapabilityCondition(capability="vision", required=False)
        context = MockContext(model_capabilities=["function_calling"])
        
        assert condition.evaluate(context) is True
    
    def test_missing_model_capabilities(self):
        """Test with missing model_capabilities attribute."""
        condition = ModelCapabilityCondition(capability="vision", required=True)
        context = MockContext()  # No model_capabilities
        
        assert condition.evaluate(context) is False


class TestCostCondition:
    """Test CostCondition."""
    
    def test_cost_within_range(self):
        """Test cost within acceptable range."""
        condition = CostCondition(max_cost=0.10, min_cost=0.01)
        context = MockContext(estimated_cost=0.05)
        
        assert condition.evaluate(context) is True
    
    def test_cost_above_max(self):
        """Test cost above maximum."""
        condition = CostCondition(max_cost=0.10, min_cost=0.01)
        context = MockContext(estimated_cost=0.15)
        
        assert condition.evaluate(context) is False
    
    def test_cost_below_min(self):
        """Test cost below minimum."""
        condition = CostCondition(max_cost=0.10, min_cost=0.01)
        context = MockContext(estimated_cost=0.001)
        
        assert condition.evaluate(context) is False
    
    def test_cost_at_boundaries(self):
        """Test cost at exact boundaries."""
        condition = CostCondition(max_cost=0.10, min_cost=0.01)
        
        context1 = MockContext(estimated_cost=0.01)
        assert condition.evaluate(context1) is True
        
        context2 = MockContext(estimated_cost=0.10)
        assert condition.evaluate(context2) is True
    
    def test_cost_negative_clamping(self):
        """Test negative cost values are clamped."""
        condition = CostCondition(max_cost=-0.5, min_cost=-0.1)
        
        assert condition.max_cost == 0.0
        assert condition.min_cost == 0.0


class TestContextTypeCondition:
    """Test ContextTypeCondition."""
    
    def test_context_type_allowed(self):
        """Test allowed context type."""
        condition = ContextTypeCondition(allowed_types=["query", "retrieval"])
        context = MockContext(context_type="query")
        
        assert condition.evaluate(context) is True
    
    def test_context_type_not_allowed(self):
        """Test disallowed context type."""
        condition = ContextTypeCondition(allowed_types=["query", "retrieval"])
        context = MockContext(context_type="generation")
        
        assert condition.evaluate(context) is False
    
    def test_empty_allowed_types(self):
        """Test with empty allowed types list."""
        condition = ContextTypeCondition(allowed_types=[])
        context = MockContext(context_type="query")
        
        assert condition.evaluate(context) is True
    
    def test_missing_context_type(self):
        """Test with missing context_type attribute."""
        condition = ContextTypeCondition(allowed_types=["query"])
        context = MockContext()  # No context_type
        
        assert condition.evaluate(context) is False  # Defaults to "unknown"


class TestCompoundCondition:
    """Test CompoundCondition."""
    
    def test_and_operator_all_true(self):
        """Test AND with all true conditions."""
        cond1 = TokenCountCondition(max_tokens=100)
        cond2 = ConfidenceCondition(min_confidence=0.5)
        condition = CompoundCondition([cond1, cond2], operator="and")
        
        context = MockContext(estimated_tokens=50, confidence_score=0.8)
        assert condition.evaluate(context) is True
    
    def test_and_operator_one_false(self):
        """Test AND with one false condition."""
        cond1 = TokenCountCondition(max_tokens=100)
        cond2 = ConfidenceCondition(min_confidence=0.9)
        condition = CompoundCondition([cond1, cond2], operator="and")
        
        context = MockContext(estimated_tokens=50, confidence_score=0.5)
        assert condition.evaluate(context) is False
    
    def test_or_operator_one_true(self):
        """Test OR with one true condition."""
        cond1 = TokenCountCondition(max_tokens=50)
        cond2 = ConfidenceCondition(min_confidence=0.5)
        condition = CompoundCondition([cond1, cond2], operator="or")
        
        context = MockContext(estimated_tokens=100, confidence_score=0.8)
        assert condition.evaluate(context) is True
    
    def test_or_operator_all_false(self):
        """Test OR with all false conditions."""
        cond1 = TokenCountCondition(max_tokens=50)
        cond2 = ConfidenceCondition(min_confidence=0.9)
        condition = CompoundCondition([cond1, cond2], operator="or")
        
        context = MockContext(estimated_tokens=100, confidence_score=0.5)
        assert condition.evaluate(context) is False
    
    def test_empty_conditions(self):
        """Test with empty conditions list."""
        condition = CompoundCondition([], operator="and")
        context = MockContext()
        
        assert condition.evaluate(context) is True
    
    def test_invalid_operator(self):
        """Test with invalid operator."""
        cond = TokenCountCondition(max_tokens=100)
        condition = CompoundCondition([cond], operator="invalid")
        context = MockContext(estimated_tokens=50)
        
        assert condition.evaluate(context) is False
    
    def test_case_insensitive_operator(self):
        """Test operators are case insensitive."""
        cond1 = TokenCountCondition(max_tokens=100)
        cond2 = ConfidenceCondition(min_confidence=0.5)
        condition = CompoundCondition([cond1, cond2], operator="AND")
        
        context = MockContext(estimated_tokens=50, confidence_score=0.8)
        assert condition.evaluate(context) is True
