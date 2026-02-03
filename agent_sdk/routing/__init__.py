"""
Routing module - Advanced decision tree routing for agent execution.

This module provides intelligent routing capabilities for dynamically selecting
execution paths based on context, confidence scores, and available tools.

Classes:
    RoutingDecisionTree: Multi-step decision tree for routing decisions
    RoutingCondition: Base class for routing conditions
    TokenCountCondition: Route based on token count
    ConfidenceCondition: Route based on model confidence
    ToolAvailabilityCondition: Route based on tool availability
    ModelCapabilityCondition: Route based on LLM capabilities
    ExecutionStrategy: Enum for execution strategies
    RoutingPath: A possible routing path
    RoutingDecision: Result of routing decision
    RoutingMetrics: Metrics for routing decisions
    RoutingAnalytics: Track routing decisions over time

Usage:
    from agent_sdk.routing import RoutingDecisionTree, ExecutionStrategy
    
    # Create a decision tree
    root_condition = TokenCountCondition(max_tokens=100)
    tree = RoutingDecisionTree("quick_path", root_condition)
    
    # Evaluate routing decision
    decision = tree.evaluate(context)
    print(f"Route: {decision.path_id}, Strategy: {decision.execution_strategy}")
"""

from agent_sdk.routing.decision_tree import RoutingDecisionTree, RoutingNode
from agent_sdk.routing.conditions import (
    RoutingCondition,
    TokenCountCondition,
    ConfidenceCondition,
    ToolAvailabilityCondition,
    ModelCapabilityCondition,
)
from agent_sdk.routing.strategies import (
    ExecutionStrategy,
    RoutingPath,
    RoutingDecision,
)
from agent_sdk.routing.metrics import RoutingMetrics, RoutingAnalytics

__all__ = [
    "RoutingDecisionTree",
    "RoutingNode",
    "RoutingCondition",
    "TokenCountCondition",
    "ConfidenceCondition",
    "ToolAvailabilityCondition",
    "ModelCapabilityCondition",
    "ExecutionStrategy",
    "RoutingPath",
    "RoutingDecision",
    "RoutingMetrics",
    "RoutingAnalytics",
]
