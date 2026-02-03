"""Conflict detection and resolution for multi-agent results."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving conflicts."""
    
    PRIORITY_BASED = "priority_based"        # Use highest priority agent
    CONFIDENCE_BASED = "confidence_based"    # Use most confident result
    VOTING = "voting"                         # Use majority vote
    MERGE = "merge"                          # Merge non-conflicting parts
    CUSTOM = "custom"                        # Custom resolution function


@dataclass
class Conflict:
    """Detected conflict between agent results."""
    
    conflict_id: str
    conflicting_agents: List[str] = field(default_factory=list)
    conflicting_values: List[Any] = field(default_factory=list)
    conflict_type: str = "value_mismatch"
    severity: float = 0.5  # 0.0-1.0
    description: str = ""
    resolution: Optional[Any] = None
    resolution_strategy: Optional[ConflictResolutionStrategy] = None
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "conflicting_agents": self.conflicting_agents,
            "conflicting_values": self.conflicting_values,
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "description": self.description,
            "resolution": self.resolution,
            "resolution_strategy": self.resolution_strategy.value if self.resolution_strategy else None,
            "resolved": self.resolved,
            "metadata": self.metadata
        }


@dataclass
class AgentResult:
    """Result from single agent."""
    
    agent_id: str
    agent_name: str
    value: Any
    priority: int = 0
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConflictAnalyzer:
    """Detects conflicts between agent results."""
    
    def __init__(self):
        """Initialize analyzer."""
        self.conflict_counter = 0
    
    def detect_conflicts(
        self,
        results: List[AgentResult],
        tolerance: float = 0.0
    ) -> List[Conflict]:
        """Detect conflicts in results.
        
        Args:
            results: Results from agents
            tolerance: Tolerance for equality (0.0-1.0)
        
        Returns:
            List of detected conflicts
        """
        conflicts: List[Conflict] = []
        
        if len(results) < 2:
            return conflicts
        
        # Compare pairwise
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                result_i = results[i]
                result_j = results[j]
                
                if self._values_conflict(result_i.value, result_j.value, tolerance):
                    conflict = self._create_conflict(
                        [result_i, result_j],
                        [result_i.value, result_j.value]
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _values_conflict(self, value1: Any, value2: Any, tolerance: float) -> bool:
        """Check if two values conflict."""
        if value1 is None or value2 is None:
            return value1 != value2
        
        # Exact match
        if value1 == value2:
            return False
        
        # Type mismatch is a conflict
        if type(value1) != type(value2):
            return True
        
        # Numeric comparison with tolerance
        if isinstance(value1, (int, float)) and isinstance(value2, (int, float)):
            diff = abs(value1 - value2)
            max_val = max(abs(value1), abs(value2))
            if max_val > 0:
                relative_diff = diff / max_val
                return relative_diff > tolerance
            return diff > tolerance
        
        # String comparison
        if isinstance(value1, str) and isinstance(value2, str):
            return value1.lower() != value2.lower()
        
        # Default: different values conflict
        return True
    
    def _create_conflict(
        self,
        results: List[AgentResult],
        values: List[Any]
    ) -> Conflict:
        """Create conflict object."""
        self.conflict_counter += 1
        
        # Determine severity
        severity = self._calculate_severity(results, values)
        
        return Conflict(
            conflict_id=f"conflict_{self.conflict_counter}",
            conflicting_agents=[r.agent_id for r in results],
            conflicting_values=values,
            conflict_type="value_mismatch",
            severity=severity,
            description=f"Agent values conflict: {values}",
            metadata={
                "agent_names": [r.agent_name for r in results],
                "agent_priorities": [r.priority for r in results],
                "agent_confidences": [r.confidence for r in results]
            }
        )
    
    def _calculate_severity(
        self,
        results: List[AgentResult],
        values: List[Any]
    ) -> float:
        """Calculate conflict severity."""
        # Higher priority difference = higher severity
        if len(results) >= 2:
            priority_diff = abs(results[0].priority - results[1].priority)
            priority_severity = min(priority_diff / 100.0, 1.0)
        else:
            priority_severity = 0.0
        
        # Higher confidence difference = higher severity
        confidences = [r.confidence for r in results]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            confidence_variance = sum(abs(c - avg_confidence) for c in confidences) / len(confidences)
        else:
            confidence_variance = 0.0
        
        # Combine factors
        severity = (priority_severity + confidence_variance) / 2
        return min(severity, 1.0)


class ConflictResolver:
    """Resolves conflicts between agent results."""
    
    def __init__(self, strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.PRIORITY_BASED):
        """Initialize resolver.
        
        Args:
            strategy: Default resolution strategy
        """
        self.strategy = strategy
        self.custom_resolvers: Dict[str, Callable] = {}
    
    def register_custom_resolver(
        self,
        name: str,
        resolver_fn: Callable[[List[AgentResult]], Any]
    ) -> None:
        """Register custom conflict resolver.
        
        Args:
            name: Name of resolver
            resolver_fn: Function that resolves conflict
        """
        self.custom_resolvers[name] = resolver_fn
    
    def resolve(
        self,
        conflict: Conflict,
        results: List[AgentResult],
        strategy: Optional[ConflictResolutionStrategy] = None,
        custom_resolver_name: Optional[str] = None
    ) -> Conflict:
        """Resolve a conflict.
        
        Args:
            conflict: Conflict to resolve
            results: Agent results involved
            strategy: Resolution strategy (uses default if None)
            custom_resolver_name: Name of custom resolver
        
        Returns:
            Resolved conflict
        """
        if custom_resolver_name and custom_resolver_name in self.custom_resolvers:
            return self._resolve_custom(conflict, results, custom_resolver_name)
        
        strategy = strategy or self.strategy
        
        if strategy == ConflictResolutionStrategy.PRIORITY_BASED:
            return self._resolve_priority_based(conflict, results)
        elif strategy == ConflictResolutionStrategy.CONFIDENCE_BASED:
            return self._resolve_confidence_based(conflict, results)
        elif strategy == ConflictResolutionStrategy.VOTING:
            return self._resolve_voting(conflict, results)
        elif strategy == ConflictResolutionStrategy.MERGE:
            return self._resolve_merge(conflict, results)
        else:
            return conflict
    
    def _resolve_priority_based(
        self,
        conflict: Conflict,
        results: List[AgentResult]
    ) -> Conflict:
        """Resolve using agent priority."""
        # Find results matching conflicting agents
        matching_results = [
            r for r in results
            if r.agent_id in conflict.conflicting_agents
        ]
        
        if not matching_results:
            return conflict
        
        # Sort by priority (highest first)
        sorted_results = sorted(matching_results, key=lambda r: r.priority, reverse=True)
        resolution = sorted_results[0].value
        
        conflict.resolution = resolution
        conflict.resolution_strategy = ConflictResolutionStrategy.PRIORITY_BASED
        conflict.resolved = True
        conflict.metadata["winner"] = sorted_results[0].agent_id
        
        return conflict
    
    def _resolve_confidence_based(
        self,
        conflict: Conflict,
        results: List[AgentResult]
    ) -> Conflict:
        """Resolve using agent confidence."""
        matching_results = [
            r for r in results
            if r.agent_id in conflict.conflicting_agents
        ]
        
        if not matching_results:
            return conflict
        
        # Sort by confidence (highest first)
        sorted_results = sorted(matching_results, key=lambda r: r.confidence, reverse=True)
        resolution = sorted_results[0].value
        
        conflict.resolution = resolution
        conflict.resolution_strategy = ConflictResolutionStrategy.CONFIDENCE_BASED
        conflict.resolved = True
        conflict.metadata["winner"] = sorted_results[0].agent_id
        conflict.metadata["confidence"] = sorted_results[0].confidence
        
        return conflict
    
    def _resolve_voting(
        self,
        conflict: Conflict,
        results: List[AgentResult]
    ) -> Conflict:
        """Resolve using majority vote."""
        # Count votes
        vote_counts: Dict[str, int] = {}
        for value in conflict.conflicting_values:
            key = str(value)
            vote_counts[key] = vote_counts.get(key, 0) + 1
        
        if not vote_counts:
            return conflict
        
        # Find majority
        max_votes = max(vote_counts.values())
        winning_value = [v for v in conflict.conflicting_values if str(v) in vote_counts and vote_counts[str(v)] == max_votes][0]
        
        conflict.resolution = winning_value
        conflict.resolution_strategy = ConflictResolutionStrategy.VOTING
        conflict.resolved = True
        conflict.metadata["votes"] = vote_counts
        
        return conflict
    
    def _resolve_merge(
        self,
        conflict: Conflict,
        results: List[AgentResult]
    ) -> Conflict:
        """Resolve by merging (if possible)."""
        # Only works for dicts
        if all(isinstance(v, dict) for v in conflict.conflicting_values):
            merged = {}
            for value in conflict.conflicting_values:
                merged.update(value)
            
            conflict.resolution = merged
            conflict.resolution_strategy = ConflictResolutionStrategy.MERGE
            conflict.resolved = True
        
        return conflict
    
    def _resolve_custom(
        self,
        conflict: Conflict,
        results: List[AgentResult],
        resolver_name: str
    ) -> Conflict:
        """Apply custom resolver."""
        try:
            resolver_fn = self.custom_resolvers[resolver_name]
            matching_results = [
                r for r in results
                if r.agent_id in conflict.conflicting_agents
            ]
            resolution = resolver_fn(matching_results)
            
            conflict.resolution = resolution
            conflict.resolution_strategy = ConflictResolutionStrategy.CUSTOM
            conflict.resolved = True
            conflict.metadata["custom_resolver"] = resolver_name
        except Exception as e:
            conflict.metadata["resolution_error"] = str(e)
        
        return conflict
