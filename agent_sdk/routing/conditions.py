"""Routing conditions for decision tree evaluation."""

from abc import abstractmethod
from typing import Any, List, Optional
from agent_sdk.routing.decision_tree import RoutingCondition


class TokenCountCondition(RoutingCondition):
    """Route based on estimated token count."""
    
    def __init__(
        self,
        max_tokens: int = 1000,
        min_tokens: int = 0,
        comparison: str = "within"
    ):
        """Initialize token count condition.
        
        Args:
            max_tokens: Maximum token threshold
            min_tokens: Minimum token threshold
            comparison: "within", "above", "below"
        """
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.comparison = comparison
    
    def evaluate(self, context: Any) -> bool:
        """Evaluate token count condition."""
        estimated_tokens = getattr(context, "estimated_tokens", 0)
        
        if self.comparison == "within":
            return self.min_tokens <= estimated_tokens <= self.max_tokens
        elif self.comparison == "above":
            return estimated_tokens > self.max_tokens
        elif self.comparison == "below":
            return estimated_tokens < self.min_tokens
        else:
            return False


class ConfidenceCondition(RoutingCondition):
    """Route based on model confidence score."""
    
    def __init__(
        self,
        min_confidence: float = 0.5,
        max_confidence: float = 1.0
    ):
        """Initialize confidence condition.
        
        Args:
            min_confidence: Minimum confidence threshold
            max_confidence: Maximum confidence threshold
        """
        self.min_confidence = max(0.0, min(1.0, min_confidence))
        self.max_confidence = max(0.0, min(1.0, max_confidence))
    
    def evaluate(self, context: Any) -> bool:
        """Evaluate confidence condition."""
        confidence = getattr(context, "confidence_score", 0.5)
        return self.min_confidence <= confidence <= self.max_confidence


class ToolAvailabilityCondition(RoutingCondition):
    """Route based on tool availability."""
    
    def __init__(
        self,
        required_tools: Optional[List[str]] = None,
        require_all: bool = True
    ):
        """Initialize tool availability condition.
        
        Args:
            required_tools: List of required tools
            require_all: True if all tools must be available
        """
        self.required_tools = required_tools or []
        self.require_all = require_all
    
    def evaluate(self, context: Any) -> bool:
        """Evaluate tool availability condition."""
        available_tools = getattr(context, "available_tools", [])
        
        if not self.required_tools:
            return True
        
        if self.require_all:
            return all(tool in available_tools for tool in self.required_tools)
        else:
            return any(tool in available_tools for tool in self.required_tools)


class ModelCapabilityCondition(RoutingCondition):
    """Route based on LLM model capabilities."""
    
    def __init__(
        self,
        capability: str,
        required: bool = True
    ):
        """Initialize model capability condition.
        
        Args:
            capability: Capability to check (e.g., "vision", "function_calling")
            required: True if capability must be present
        """
        self.capability = capability
        self.required = required
    
    def evaluate(self, context: Any) -> bool:
        """Evaluate model capability condition."""
        capabilities = getattr(context, "model_capabilities", [])
        has_capability = self.capability in capabilities
        
        if self.required:
            return has_capability
        else:
            return not has_capability


class CostCondition(RoutingCondition):
    """Route based on estimated operation cost."""
    
    def __init__(
        self,
        max_cost: float = 0.01,
        min_cost: float = 0.0
    ):
        """Initialize cost condition.
        
        Args:
            max_cost: Maximum acceptable cost
            min_cost: Minimum acceptable cost
        """
        self.max_cost = max(0.0, max_cost)
        self.min_cost = max(0.0, min_cost)
    
    def evaluate(self, context: Any) -> bool:
        """Evaluate cost condition."""
        estimated_cost = getattr(context, "estimated_cost", 0.0)
        return self.min_cost <= estimated_cost <= self.max_cost


class ContextTypeCondition(RoutingCondition):
    """Route based on context type."""
    
    def __init__(
        self,
        allowed_types: Optional[List[str]] = None
    ):
        """Initialize context type condition.
        
        Args:
            allowed_types: List of allowed context types
        """
        self.allowed_types = allowed_types or []
    
    def evaluate(self, context: Any) -> bool:
        """Evaluate context type condition."""
        context_type = getattr(context, "context_type", "unknown")
        
        if not self.allowed_types:
            return True
        
        return context_type in self.allowed_types


class CompoundCondition(RoutingCondition):
    """Combine multiple conditions with AND/OR logic."""
    
    def __init__(
        self,
        conditions: List[RoutingCondition],
        operator: str = "and"
    ):
        """Initialize compound condition.
        
        Args:
            conditions: List of conditions to combine
            operator: "and" or "or"
        """
        self.conditions = conditions
        self.operator = operator.lower()
    
    def evaluate(self, context: Any) -> bool:
        """Evaluate compound condition."""
        if not self.conditions:
            return True
        
        results = [cond.evaluate(context) for cond in self.conditions]
        
        if self.operator == "and":
            return all(results)
        elif self.operator == "or":
            return any(results)
        else:
            return False
