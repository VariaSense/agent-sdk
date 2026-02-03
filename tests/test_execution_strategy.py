"""Tests for execution strategies and routing decisions."""

import pytest
from agent_sdk.routing.strategies import (
    ExecutionStrategy,
    RoutingPath,
    RoutingDecision,
    StrategySelector,
)


class MockContext:
    """Mock execution context for testing."""
    
    def __init__(self, **kwargs):
        self.estimated_tokens = kwargs.get("estimated_tokens", 100)
        self.confidence_score = kwargs.get("confidence_score", 0.8)
        self.available_tools = kwargs.get("available_tools", [])
        self.estimated_cost = kwargs.get("estimated_cost", 0.05)
        self.context_type = kwargs.get("context_type", "query")
        self.model_capabilities = kwargs.get("model_capabilities", [])
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestExecutionStrategy:
    """Test ExecutionStrategy enum."""
    
    def test_execution_strategy_values(self):
        """Test all execution strategies are defined."""
        assert hasattr(ExecutionStrategy, "DIRECT")
        assert hasattr(ExecutionStrategy, "PARALLEL")
        assert hasattr(ExecutionStrategy, "SEQUENTIAL")
        assert hasattr(ExecutionStrategy, "FAILOVER")
        assert hasattr(ExecutionStrategy, "ROUND_ROBIN")
        assert hasattr(ExecutionStrategy, "RANDOM")
    
    def test_execution_strategy_direct_value(self):
        """Test DIRECT strategy value."""
        assert ExecutionStrategy.DIRECT.value == "direct"
    
    def test_execution_strategy_parallel_value(self):
        """Test PARALLEL strategy value."""
        assert ExecutionStrategy.PARALLEL.value == "parallel"
    
    def test_execution_strategy_sequential_value(self):
        """Test SEQUENTIAL strategy value."""
        assert ExecutionStrategy.SEQUENTIAL.value == "sequential"
    
    def test_execution_strategy_failover_value(self):
        """Test FAILOVER strategy value."""
        assert ExecutionStrategy.FAILOVER.value == "failover"
    
    def test_execution_strategy_round_robin_value(self):
        """Test ROUND_ROBIN strategy value."""
        assert ExecutionStrategy.ROUND_ROBIN.value == "round_robin"
    
    def test_execution_strategy_random_value(self):
        """Test RANDOM strategy value."""
        assert ExecutionStrategy.RANDOM.value == "random"


class TestRoutingPath:
    """Test RoutingPath dataclass."""
    
    def test_routing_path_creation(self):
        """Test basic RoutingPath creation."""
        path = RoutingPath(
            path_id="test_path",
            target_model="gpt-4"
        )
        
        assert path.path_id == "test_path"
        assert path.target_model == "gpt-4"
    
    def test_routing_path_defaults(self):
        """Test RoutingPath default values."""
        path = RoutingPath(path_id="test")
        
        assert path.path_id == "test"
        assert path.target_model == ""
        assert path.priority == 0
        assert path.cost_estimate == 0.0
        assert path.success_rate == 1.0
        assert path.target_tool_set == []
        assert path.metadata == {}
    
    def test_routing_path_with_cost(self):
        """Test RoutingPath with cost estimate."""
        path = RoutingPath(
            path_id="expensive",
            target_model="gpt-4",
            cost_estimate=0.50
        )
        
        assert path.cost_estimate == 0.50
    
    def test_routing_path_with_success_rate(self):
        """Test RoutingPath with success rate."""
        path = RoutingPath(
            path_id="unreliable",
            target_model="gpt-3",
            success_rate=0.7
        )
        
        assert path.success_rate == 0.7
    
    def test_routing_path_to_dict(self):
        """Test RoutingPath conversion to dict."""
        path = RoutingPath(
            path_id="test",
            target_model="gpt-4",
            priority=5,
            cost_estimate=0.1,
            success_rate=0.9
        )
        
        path_dict = path.to_dict()
        assert path_dict["path_id"] == "test"
        assert path_dict["target_model"] == "gpt-4"
        assert path_dict["priority"] == 5
        assert path_dict["cost_estimate"] == 0.1
        assert path_dict["success_rate"] == 0.9


class TestRoutingDecision:
    """Test RoutingDecision dataclass."""
    
    def test_routing_decision_creation(self):
        """Test basic RoutingDecision creation."""
        decision = RoutingDecision(
            path_id="selected_path",
            target_model="gpt-4",
            tool_set=["web_search"],
            confidence=0.95,
            decision_trace=["step1", "step2"]
        )
        
        assert decision.path_id == "selected_path"
        assert decision.target_model == "gpt-4"
        assert decision.tool_set == ["web_search"]
        assert decision.confidence == 0.95
        assert decision.decision_trace == ["step1", "step2"]
    
    def test_routing_decision_defaults(self):
        """Test RoutingDecision default values."""
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-3",
            tool_set=[],
            confidence=1.0,
            decision_trace=[]
        )
        
        assert decision.execution_strategy == "direct"
        assert decision.alternative_paths == []
        assert decision.metadata == {}
    
    def test_routing_decision_with_alternatives(self):
        """Test RoutingDecision with alternative paths."""
        decision = RoutingDecision(
            path_id="primary",
            target_model="gpt-4",
            tool_set=["web_search"],
            confidence=0.85,
            decision_trace=[],
            alternative_paths=["alt1", "alt2"]
        )
        
        assert len(decision.alternative_paths) == 2
        assert decision.alternative_paths[0] == "alt1"
    
    def test_routing_decision_confidence(self):
        """Test RoutingDecision confidence score."""
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.85,
            decision_trace=[]
        )
        
        assert decision.confidence == 0.85
    
    def test_routing_decision_metadata(self):
        """Test RoutingDecision with metadata."""
        metadata = {"reason": "high_confidence", "latency_ms": 45}
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=1.0,
            decision_trace=[],
            metadata=metadata
        )
        
        assert decision.metadata["reason"] == "high_confidence"
        assert decision.metadata["latency_ms"] == 45
    
    def test_routing_decision_to_dict(self):
        """Test RoutingDecision conversion to dict."""
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=["search"],
            confidence=0.9,
            decision_trace=["evaluated", "selected"]
        )
        
        decision_dict = decision.to_dict()
        assert decision_dict["path_id"] == "test"
        assert decision_dict["target_model"] == "gpt-4"
        assert decision_dict["tool_set"] == ["search"]
        assert decision_dict["confidence"] == 0.9
        assert decision_dict["decision_trace"] == ["evaluated", "selected"]


class TestStrategySelector:
    """Test StrategySelector."""
    
    def test_strategy_selector_creation(self):
        """Test StrategySelector initialization."""
        selector = StrategySelector()
        assert isinstance(selector, StrategySelector)
    
    def test_select_strategy_direct_high_confidence(self):
        """Test DIRECT strategy for high confidence single path."""
        selector = StrategySelector()
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.95,
            decision_trace=[]
        )
        context = MockContext()
        
        strategy = selector.select_strategy(decision, context, num_available_paths=1)
        assert strategy == ExecutionStrategy.DIRECT
    
    def test_select_strategy_multiple_paths_default(self):
        """Test strategy with multiple paths defaults to PARALLEL."""
        selector = StrategySelector()
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.5,
            decision_trace=[]
        )
        context = MockContext()
        
        strategy = selector.select_strategy(decision, context, num_available_paths=3)
        assert strategy == ExecutionStrategy.PARALLEL
    
    def test_select_strategy_time_critical_parallel(self):
        """Test PARALLEL strategy for time-critical requests."""
        selector = StrategySelector()
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.7,
            decision_trace=[]
        )
        context = MockContext(time_critical=True)
        
        strategy = selector.select_strategy(decision, context, num_available_paths=2)
        assert strategy == ExecutionStrategy.PARALLEL
    
    def test_select_strategy_cost_critical_sequential(self):
        """Test SEQUENTIAL strategy for cost-critical requests."""
        selector = StrategySelector()
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.7,
            decision_trace=[]
        )
        context = MockContext(cost_critical=True)
        
        strategy = selector.select_strategy(decision, context, num_available_paths=2)
        assert strategy == ExecutionStrategy.SEQUENTIAL
    
    def test_select_strategy_reliability_failover(self):
        """Test FAILOVER strategy for reliability-critical requests."""
        selector = StrategySelector()
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.7,
            decision_trace=[]
        )
        context = MockContext(requires_reliability=True)
        
        strategy = selector.select_strategy(decision, context, num_available_paths=2)
        assert strategy == ExecutionStrategy.FAILOVER
    
    def test_add_custom_rule(self):
        """Test adding custom strategy rules."""
        selector = StrategySelector()
        
        def custom_condition(decision, context):
            return decision.confidence > 0.9
        
        selector.add_rule("high_confidence", custom_condition, ExecutionStrategy.DIRECT)
        assert "high_confidence" in selector.strategy_rules
    
    def test_evaluate_custom_rules_match(self):
        """Test evaluating custom rules that match."""
        selector = StrategySelector()
        
        def custom_condition(decision, context):
            return decision.confidence > 0.8
        
        selector.add_rule("high_confidence", custom_condition, ExecutionStrategy.DIRECT)
        
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.95,
            decision_trace=[]
        )
        context = MockContext()
        
        strategy = selector.evaluate_custom_rules(decision, context)
        assert strategy == ExecutionStrategy.DIRECT
    
    def test_evaluate_custom_rules_no_match(self):
        """Test evaluating custom rules that don't match."""
        selector = StrategySelector()
        
        def custom_condition(decision, context):
            return decision.confidence > 0.99
        
        selector.add_rule("very_high_confidence", custom_condition, ExecutionStrategy.DIRECT)
        
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.85,
            decision_trace=[]
        )
        context = MockContext()
        
        strategy = selector.evaluate_custom_rules(decision, context)
        assert strategy is None
    
    def test_evaluate_custom_rules_exception_handling(self):
        """Test custom rules that raise exceptions are skipped."""
        selector = StrategySelector()
        
        def faulty_condition(decision, context):
            raise ValueError("Intentional error")
        
        def working_condition(decision, context):
            return True
        
        selector.add_rule("faulty", faulty_condition, ExecutionStrategy.DIRECT)
        selector.add_rule("working", working_condition, ExecutionStrategy.PARALLEL)
        
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.85,
            decision_trace=[]
        )
        context = MockContext()
        
        strategy = selector.evaluate_custom_rules(decision, context)
        assert strategy == ExecutionStrategy.PARALLEL
    
    def test_single_path_direct_strategy(self):
        """Test single path always returns DIRECT."""
        selector = StrategySelector()
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.5,
            decision_trace=[]
        )
        context = MockContext()
        
        strategy = selector.select_strategy(decision, context, num_available_paths=1)
        assert strategy == ExecutionStrategy.DIRECT


class TestStrategyMetadata:
    """Test strategy metadata and scoring."""
    
    def test_routing_path_score_calculation(self):
        """Test implicit score calculation for paths."""
        path1 = RoutingPath(
            path_id="path1",
            target_model="gpt-4",
            priority=10,
            success_rate=0.8
        )
        path2 = RoutingPath(
            path_id="path2",
            target_model="gpt-3",
            priority=5,
            success_rate=0.95
        )
        
        # Higher priority and success rate should be preferred
        assert path1.priority > path2.priority
        assert path2.success_rate > path1.success_rate
    
    def test_routing_decision_trace_building(self):
        """Test RoutingDecision trace includes decision steps."""
        trace = [
            "evaluating_conditions",
            "selecting_path",
            "calculating_strategy",
            "confirmed"
        ]
        decision = RoutingDecision(
            path_id="test",
            target_model="gpt-4",
            tool_set=[],
            confidence=0.9,
            decision_trace=trace
        )
        
        assert len(decision.decision_trace) == 4
        assert decision.decision_trace[0] == "evaluating_conditions"
        assert decision.decision_trace[-1] == "confirmed"
