"""Tests for routing decision tree functionality."""

import pytest
from datetime import datetime
from agent_sdk.routing.decision_tree import (
    RoutingDecisionTree,
    RoutingNode,
    RoutingPath,
    RoutingCondition,
    RoutingDecision,
)
from agent_sdk.routing.conditions import (
    TokenCountCondition,
    ConfidenceCondition,
)


class MockContext:
    """Mock execution context for testing."""
    
    def __init__(
        self,
        estimated_tokens: int = 100,
        confidence_score: float = 0.8,
        available_tools: list = None,
        model_capabilities: list = None,
        estimated_cost: float = 0.01,
        context_type: str = "default"
    ):
        self.estimated_tokens = estimated_tokens
        self.confidence_score = confidence_score
        self.available_tools = available_tools or []
        self.model_capabilities = model_capabilities or []
        self.estimated_cost = estimated_cost
        self.context_type = context_type


class TestRoutingPath:
    """Test RoutingPath dataclass."""
    
    def test_create_path(self):
        """Test creating a routing path."""
        path = RoutingPath(
            path_id="fast_path",
            target_model="gpt-4",
            target_tool_set=["search", "calculator"],
            priority=10
        )
        
        assert path.path_id == "fast_path"
        assert path.target_model == "gpt-4"
        assert path.target_tool_set == ["search", "calculator"]
        assert path.priority == 10
    
    def test_path_to_dict(self):
        """Test converting path to dictionary."""
        path = RoutingPath(
            path_id="test_path",
            target_model="gpt-3.5-turbo",
            target_tool_set=["tool1"],
            priority=5,
            metadata={"key": "value"}
        )
        
        result = path.to_dict()
        
        assert result["path_id"] == "test_path"
        assert result["target_model"] == "gpt-3.5-turbo"
        assert result["target_tool_set"] == ["tool1"]
        assert result["priority"] == 5
        assert result["metadata"]["key"] == "value"
    
    def test_path_defaults(self):
        """Test path default values."""
        path = RoutingPath(path_id="minimal")
        
        assert path.target_model == ""
        assert path.target_tool_set == []
        assert path.priority == 0
        assert path.metadata == {}


class TestRoutingNode:
    """Test RoutingNode class."""
    
    def test_create_node(self):
        """Test creating a routing node."""
        condition = TokenCountCondition(max_tokens=100)
        node = RoutingNode(
            node_id="node1",
            condition=condition
        )
        
        assert node.node_id == "node1"
        assert node.condition == condition
        assert node.true_path is None
        assert node.false_path is None
    
    def test_node_evaluate_condition_true(self):
        """Test evaluating node with true condition."""
        condition = TokenCountCondition(max_tokens=200)
        node = RoutingNode(
            node_id="test_node",
            condition=condition
        )
        
        context = MockContext(estimated_tokens=100)
        result, trace = node.evaluate(context)
        
        assert result is True
        assert "test_node" in trace[0]
        assert "TokenCountCondition" in trace[0]
    
    def test_node_evaluate_condition_false(self):
        """Test evaluating node with false condition."""
        condition = TokenCountCondition(max_tokens=50)
        node = RoutingNode(
            node_id="test_node",
            condition=condition
        )
        
        context = MockContext(estimated_tokens=100)
        result, trace = node.evaluate(context)
        
        assert result is False
        assert "test_node" in trace[0]
    
    def test_node_evaluate_with_exception(self):
        """Test node evaluation handling exceptions."""
        class BrokenCondition(RoutingCondition):
            def evaluate(self, context):
                raise ValueError("Test error")
        
        condition = BrokenCondition()
        node = RoutingNode(node_id="broken", condition=condition)
        
        context = MockContext()
        result, trace = node.evaluate(context)
        
        assert result is False
        assert "ERROR" in trace[0]


class TestRoutingDecisionTree:
    """Test RoutingDecisionTree class."""
    
    def test_create_tree(self):
        """Test creating a routing decision tree."""
        condition = TokenCountCondition(max_tokens=100)
        tree = RoutingDecisionTree(
            name="test_tree",
            root_condition=condition
        )
        
        assert tree.name == "test_tree"
        assert tree.root_condition == condition
        assert tree.nodes == []
        assert tree.paths == {}
    
    def test_add_path_to_tree(self):
        """Test adding paths to tree."""
        tree = RoutingDecisionTree(name="test")
        path = RoutingPath(
            path_id="path1",
            target_model="gpt-4",
            priority=10
        )
        
        tree.add_path(path)
        
        assert "path1" in tree.paths
        assert tree.paths["path1"] == path
    
    def test_get_path(self):
        """Test retrieving path from tree."""
        tree = RoutingDecisionTree(name="test")
        path = RoutingPath(path_id="test_path", target_model="gpt-4")
        tree.add_path(path)
        
        retrieved = tree.get_path("test_path")
        
        assert retrieved == path
        assert retrieved is not None
    
    def test_get_nonexistent_path(self):
        """Test retrieving nonexistent path."""
        tree = RoutingDecisionTree(name="test")
        
        result = tree.get_path("nonexistent")
        
        assert result is None
    
    def test_add_node_to_tree(self):
        """Test adding nodes to tree."""
        tree = RoutingDecisionTree(name="test")
        condition = TokenCountCondition(max_tokens=100)
        node = RoutingNode(node_id="node1", condition=condition)
        
        tree.add_node(node)
        
        assert len(tree.nodes) == 1
        assert tree.nodes[0] == node
    
    def test_evaluate_tree_with_matching_path(self):
        """Test tree evaluation with matching path."""
        tree = RoutingDecisionTree(name="test_tree")
        path = RoutingPath(
            path_id="optimal_path",
            target_model="gpt-4",
            target_tool_set=["search"],
            priority=10
        )
        tree.add_path(path)
        
        context = MockContext(estimated_tokens=100)
        decision = tree.evaluate(context)
        
        assert decision.path_id == "optimal_path"
        assert decision.target_model == "gpt-4"
        assert decision.tool_set == ["search"]
        assert decision.confidence > 0.0
    
    def test_evaluate_tree_with_default_path(self):
        """Test tree evaluation falling back to default path."""
        tree = RoutingDecisionTree(name="test_tree")
        tree.add_path(RoutingPath(
            path_id="default",
            target_model="gpt-3.5-turbo"
        ))
        
        context = MockContext()
        decision = tree.evaluate(context, default_path_id="default")
        
        assert decision.path_id == "default"
    
    def test_evaluate_tree_no_paths(self):
        """Test tree evaluation with no paths."""
        tree = RoutingDecisionTree(name="empty_tree")
        
        context = MockContext()
        decision = tree.evaluate(context)
        
        assert decision.path_id == "default"
        assert decision.target_model == "default"
    
    def test_validate_tree_valid(self):
        """Test validating a valid tree."""
        tree = RoutingDecisionTree(name="test")
        tree.add_path(RoutingPath(
            path_id="path1",
            target_model="gpt-4"
        ))
        
        assert tree.validate_tree() is True
    
    def test_validate_tree_no_paths(self):
        """Test validating tree with no paths."""
        tree = RoutingDecisionTree(name="empty")
        
        assert tree.validate_tree() is False
    
    def test_validate_tree_invalid_path(self):
        """Test validating tree with invalid paths."""
        tree = RoutingDecisionTree(name="test")
        tree.add_path(RoutingPath(path_id="", target_model=""))
        
        assert tree.validate_tree() is False
    
    def test_get_path_trace(self):
        """Test getting path trace."""
        tree = RoutingDecisionTree(name="test")
        tree.add_path(RoutingPath(path_id="path1", target_model="gpt-4"))
        tree.add_path(RoutingPath(path_id="path2", target_model="gpt-3.5"))
        
        trace = tree.get_path_trace()
        
        assert len(trace) == 2
        assert "path1" in trace
        assert "path2" in trace
    
    def test_tree_to_dict(self):
        """Test converting tree to dictionary."""
        tree = RoutingDecisionTree(name="test_tree")
        tree.add_path(RoutingPath(
            path_id="path1",
            target_model="gpt-4",
            priority=5
        ))
        
        result = tree.to_dict()
        
        assert result["name"] == "test_tree"
        assert result["num_paths"] == 1
        assert result["num_nodes"] == 0
        assert len(result["paths"]) == 1
    
    def test_tree_multiple_paths_priority_selection(self):
        """Test tree selects path with highest priority."""
        tree = RoutingDecisionTree(name="test")
        tree.add_path(RoutingPath(
            path_id="low_priority",
            target_model="gpt-3.5-turbo",
            priority=1
        ))
        tree.add_path(RoutingPath(
            path_id="high_priority",
            target_model="gpt-4",
            priority=10
        ))
        
        context = MockContext()
        decision = tree.evaluate(context)
        
        assert decision.path_id == "high_priority"
        assert decision.target_model == "gpt-4"
    
    def test_evaluate_tree_with_root_condition(self):
        """Test tree evaluation with root condition."""
        condition = ConfidenceCondition(min_confidence=0.5)
        tree = RoutingDecisionTree(name="test", root_condition=condition)
        tree.add_path(RoutingPath(
            path_id="path1",
            target_model="gpt-4"
        ))
        
        context = MockContext(confidence_score=0.8)
        decision = tree.evaluate(context)
        
        assert decision.path_id == "path1"
        assert len(decision.decision_trace) > 0
    
    def test_routing_decision_to_dict(self):
        """Test RoutingDecision conversion to dict."""
        decision = RoutingDecision(
            path_id="test_path",
            target_model="gpt-4",
            tool_set=["search"],
            confidence=0.95,
            decision_trace=["trace1", "trace2"],
            execution_strategy="parallel",
            metadata={"key": "value"}
        )
        
        result = decision.to_dict()
        
        assert result["path_id"] == "test_path"
        assert result["target_model"] == "gpt-4"
        assert result["confidence"] == 0.95
        assert "timestamp" in result
    
    def test_tree_metadata(self):
        """Test tree metadata storage."""
        tree = RoutingDecisionTree(name="test")
        tree.metadata["custom_key"] = "custom_value"
        
        assert tree.metadata["custom_key"] == "custom_value"
