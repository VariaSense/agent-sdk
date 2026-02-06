"""Routing decision tree engine for intelligent path selection."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum


class RoutingDecision:
    """Result of routing decision evaluation."""
    
    def __init__(
        self,
        path_id: str,
        target_model: str,
        tool_set: List[str],
        confidence: float,
        decision_trace: List[str],
        execution_strategy: str = "direct",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize routing decision."""
        self.path_id = path_id
        self.target_model = target_model
        self.tool_set = tool_set
        self.confidence = confidence
        self.decision_trace = decision_trace
        self.execution_strategy = execution_strategy
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path_id": self.path_id,
            "target_model": self.target_model,
            "tool_set": self.tool_set,
            "confidence": self.confidence,
            "decision_trace": self.decision_trace,
            "execution_strategy": self.execution_strategy,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class RoutingNode:
    """Node in routing decision tree."""
    
    def __init__(
        self,
        node_id: str,
        condition: "RoutingCondition",
        true_path: Optional["RoutingPath"] = None,
        false_path: Optional["RoutingPath"] = None
    ):
        """Initialize routing node."""
        self.node_id = node_id
        self.condition = condition
        self.true_path = true_path
        self.false_path = false_path
        self.metadata: Dict[str, Any] = {}
    
    def evaluate(self, context: Any) -> tuple[bool, List[str]]:
        """Evaluate condition and return result with trace."""
        try:
            result = self.condition.evaluate(context)
            trace = [f"Node {self.node_id}: {self.condition.__class__.__name__} = {result}"]
            return result, trace
        except Exception as e:
            trace = [f"Node {self.node_id}: ERROR - {str(e)}"]
            return False, trace


@dataclass
class RoutingPath:
    """A possible routing path in decision tree."""
    path_id: str
    condition: Optional["RoutingCondition"] = None
    target_model: str = ""
    target_tool_set: List[str] = field(default_factory=list)
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path_id": self.path_id,
            "target_model": self.target_model,
            "target_tool_set": self.target_tool_set,
            "priority": self.priority,
            "metadata": self.metadata
        }


class RoutingDecisionTree:
    """Multi-step decision tree for routing decisions."""
    
    def __init__(
        self,
        name: str,
        root_condition: Optional["RoutingCondition"] = None
    ):
        """Initialize decision tree."""
        self.name = name
        self.root_condition = root_condition
        self.nodes: List[RoutingNode] = []
        self.paths: Dict[str, RoutingPath] = {}
        self.metadata: Dict[str, Any] = {}
        self.created_at = datetime.now(timezone.utc)
    
    def add_node(self, node: RoutingNode) -> None:
        """Add node to tree."""
        self.nodes.append(node)
    
    def add_path(self, path: RoutingPath) -> None:
        """Add routing path to tree."""
        self.paths[path.path_id] = path
    
    def get_path(self, path_id: str) -> Optional[RoutingPath]:
        """Get path by ID."""
        return self.paths.get(path_id)
    
    def evaluate(
        self,
        context: Any,
        default_path_id: str = "default"
    ) -> RoutingDecision:
        """Evaluate decision tree against context.
        
        Args:
            context: Execution context to evaluate
            default_path_id: Default path if no match found
        
        Returns:
            RoutingDecision with routing result and trace
        """
        trace: List[str] = []
        confidence = 1.0
        
        # Evaluate root condition if present
        if self.root_condition:
            try:
                result, node_trace = self._evaluate_condition(
                    self.root_condition, context
                )
                trace.extend(node_trace)
                confidence *= (1.0 if result else 0.5)
            except Exception as e:
                trace.append(f"Error evaluating root condition: {str(e)}")
                confidence = 0.5
        
        # Select best path
        selected_path = self._select_best_path(context, trace)
        
        if not selected_path:
            selected_path = self.paths.get(default_path_id)
        
        if not selected_path:
            # Create default path
            selected_path = RoutingPath(
                path_id=default_path_id,
                target_model="default",
                target_tool_set=[],
                priority=0
            )
        
        # Determine execution strategy
        execution_strategy = self._determine_strategy(context, selected_path)
        
        return RoutingDecision(
            path_id=selected_path.path_id,
            target_model=selected_path.target_model,
            tool_set=selected_path.target_tool_set,
            confidence=max(0.0, min(1.0, confidence)),
            decision_trace=trace,
            execution_strategy=execution_strategy,
            metadata=selected_path.metadata
        )
    
    def _evaluate_condition(
        self,
        condition: "RoutingCondition",
        context: Any
    ) -> tuple[bool, List[str]]:
        """Evaluate a condition against context."""
        result = condition.evaluate(context)
        trace = [f"Condition {condition.__class__.__name__}: {result}"]
        return result, trace
    
    def _select_best_path(
        self,
        context: Any,
        trace: List[str]
    ) -> Optional[RoutingPath]:
        """Select best path based on context."""
        if not self.paths:
            return None
        
        # Simple selection: return highest priority path
        best_path = None
        best_priority = -1
        
        for path in self.paths.values():
            if path.priority > best_priority:
                best_priority = path.priority
                best_path = path
        
        if best_path:
            trace.append(f"Selected path: {best_path.path_id} (priority {best_path.priority})")
        
        return best_path
    
    def _determine_strategy(
        self,
        context: Any,
        path: RoutingPath
    ) -> str:
        """Determine execution strategy."""
        # Simple heuristic: use direct strategy by default
        return "direct"
    
    def validate_tree(self) -> bool:
        """Validate tree structure."""
        if not self.paths:
            return False
        
        # Check all paths have required fields
        for path in self.paths.values():
            if not path.path_id or not path.target_model:
                return False
        
        return True
    
    def get_path_trace(self) -> List[str]:
        """Get trace of paths in tree."""
        return [p.path_id for p in self.paths.values()]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tree to dictionary."""
        return {
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "num_nodes": len(self.nodes),
            "num_paths": len(self.paths),
            "paths": [p.to_dict() for p in self.paths.values()],
            "metadata": self.metadata
        }


# Define RoutingCondition here to avoid circular imports
class RoutingCondition(ABC):
    """Base class for routing conditions."""
    
    @abstractmethod
    def evaluate(self, context: Any) -> bool:
        """Evaluate condition against context.
        
        Args:
            context: Execution context
        
        Returns:
            bool: True if condition is met
        """
        pass
