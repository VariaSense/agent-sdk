"""Execution strategies for routing decisions."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ExecutionStrategy(Enum):
    """Execution strategy types."""
    
    DIRECT = "direct"              # Single execution path
    PARALLEL = "parallel"          # Multiple paths simultaneously
    SEQUENTIAL = "sequential"      # Multiple paths in sequence
    FAILOVER = "failover"          # Try primary, fallback to secondary
    ROUND_ROBIN = "round_robin"    # Distribute across paths
    RANDOM = "random"              # Random path selection


@dataclass
class RoutingPath:
    """A possible routing path in decision tree."""
    path_id: str
    target_model: str = ""
    target_tool_set: List[str] = field(default_factory=list)
    priority: int = 0
    cost_estimate: float = 0.0
    success_rate: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path_id": self.path_id,
            "target_model": self.target_model,
            "target_tool_set": self.target_tool_set,
            "priority": self.priority,
            "cost_estimate": self.cost_estimate,
            "success_rate": self.success_rate,
            "metadata": self.metadata
        }


@dataclass
class RoutingDecision:
    """Result of routing decision."""
    path_id: str
    target_model: str
    tool_set: List[str]
    confidence: float
    decision_trace: List[str]
    execution_strategy: str = "direct"
    alternative_paths: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path_id": self.path_id,
            "target_model": self.target_model,
            "tool_set": self.tool_set,
            "confidence": self.confidence,
            "decision_trace": self.decision_trace,
            "execution_strategy": self.execution_strategy,
            "alternative_paths": self.alternative_paths,
            "metadata": self.metadata
        }


class StrategySelector:
    """Select execution strategy based on context and decision."""
    
    def __init__(self):
        """Initialize strategy selector."""
        self.strategy_rules: Dict[str, Any] = {}
    
    def select_strategy(
        self,
        decision: RoutingDecision,
        context: Any,
        num_available_paths: int = 1
    ) -> ExecutionStrategy:
        """Select best execution strategy.
        
        Args:
            decision: Routing decision
            context: Execution context
            num_available_paths: Number of available paths
        
        Returns:
            Selected ExecutionStrategy
        """
        # High confidence, single path -> DIRECT
        if decision.confidence > 0.8 and num_available_paths == 1:
            return ExecutionStrategy.DIRECT
        
        # Multiple paths, time-critical -> PARALLEL
        if num_available_paths > 1 and hasattr(context, "time_critical") and context.time_critical:
            return ExecutionStrategy.PARALLEL
        
        # Multiple paths, cost-critical -> SEQUENTIAL
        if num_available_paths > 1 and hasattr(context, "cost_critical") and context.cost_critical:
            return ExecutionStrategy.SEQUENTIAL
        
        # Multiple paths, high reliability needed -> FAILOVER
        if num_available_paths > 1 and hasattr(context, "requires_reliability") and context.requires_reliability:
            return ExecutionStrategy.FAILOVER
        
        # Default to DIRECT for single path, PARALLEL for multiple
        return ExecutionStrategy.PARALLEL if num_available_paths > 1 else ExecutionStrategy.DIRECT
    
    def add_rule(
        self,
        rule_name: str,
        condition_fn,
        strategy: ExecutionStrategy
    ) -> None:
        """Add custom strategy rule.
        
        Args:
            rule_name: Name of rule
            condition_fn: Function that evaluates to bool
            strategy: Strategy to select if condition is met
        """
        self.strategy_rules[rule_name] = {
            "condition": condition_fn,
            "strategy": strategy
        }
    
    def evaluate_custom_rules(
        self,
        decision: RoutingDecision,
        context: Any
    ) -> Optional[ExecutionStrategy]:
        """Evaluate custom strategy rules.
        
        Args:
            decision: Routing decision
            context: Execution context
        
        Returns:
            Selected strategy or None if no rule matches
        """
        for rule_name, rule_def in self.strategy_rules.items():
            try:
                if rule_def["condition"](decision, context):
                    return rule_def["strategy"]
            except Exception:
                # Skip rules that raise exceptions
                continue
        
        return None
