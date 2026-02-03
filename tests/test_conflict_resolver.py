"""Tests for conflict resolver."""

import pytest
from agent_sdk.coordination.conflict_resolver import (
    ConflictResolutionStrategy,
    Conflict,
    AgentResult,
    ConflictAnalyzer,
    ConflictResolver
)


class TestConflict:
    """Tests for Conflict."""
    
    def test_creation(self):
        """Test conflict creation."""
        conflict = Conflict(
            conflict_id="c1",
            conflicting_agents=["agent1", "agent2"],
            conflicting_values=[1, 2]
        )
        
        assert conflict.conflict_id == "c1"
        assert len(conflict.conflicting_agents) == 2
        assert not conflict.resolved
    
    def test_to_dict(self):
        """Test serialization."""
        conflict = Conflict(
            conflict_id="c1",
            conflicting_agents=["agent1", "agent2"],
            conflicting_values=[1, 2],
            resolution_strategy=ConflictResolutionStrategy.PRIORITY_BASED
        )
        
        d = conflict.to_dict()
        
        assert d["conflict_id"] == "c1"
        assert d["resolution_strategy"] == "priority_based"


class TestAgentResult:
    """Tests for AgentResult."""
    
    def test_creation(self):
        """Test agent result creation."""
        result = AgentResult(
            agent_id="a1",
            agent_name="Agent 1",
            value=42,
            priority=10,
            confidence=0.95
        )
        
        assert result.agent_id == "a1"
        assert result.value == 42
        assert result.priority == 10
        assert result.confidence == 0.95


class TestConflictAnalyzer:
    """Tests for ConflictAnalyzer."""
    
    def test_initialization(self):
        """Test analyzer creation."""
        analyzer = ConflictAnalyzer()
        
        assert analyzer.conflict_counter == 0
    
    def test_no_conflict_same_values(self):
        """Test no conflict when values match."""
        analyzer = ConflictAnalyzer()
        
        results = [
            AgentResult("a1", "Agent 1", 42),
            AgentResult("a2", "Agent 2", 42),
        ]
        
        conflicts = analyzer.detect_conflicts(results)
        
        assert len(conflicts) == 0
    
    def test_conflict_different_values(self):
        """Test conflict detection."""
        analyzer = ConflictAnalyzer()
        
        results = [
            AgentResult("a1", "Agent 1", 42),
            AgentResult("a2", "Agent 2", 43),
        ]
        
        conflicts = analyzer.detect_conflicts(results)
        
        assert len(conflicts) == 1
        assert conflicts[0].conflicting_agents == ["a1", "a2"]
    
    def test_conflict_none_values(self):
        """Test conflict with None values."""
        analyzer = ConflictAnalyzer()
        
        results = [
            AgentResult("a1", "Agent 1", None),
            AgentResult("a2", "Agent 2", 42),
        ]
        
        conflicts = analyzer.detect_conflicts(results)
        
        assert len(conflicts) == 1
    
    def test_conflict_type_mismatch(self):
        """Test conflict with type mismatch."""
        analyzer = ConflictAnalyzer()
        
        results = [
            AgentResult("a1", "Agent 1", 42),
            AgentResult("a2", "Agent 2", "42"),
        ]
        
        conflicts = analyzer.detect_conflicts(results)
        
        assert len(conflicts) == 1
    
    def test_no_conflict_numeric_tolerance(self):
        """Test numeric comparison with tolerance."""
        analyzer = ConflictAnalyzer()
        
        results = [
            AgentResult("a1", "Agent 1", 100.0),
            AgentResult("a2", "Agent 2", 100.1),
        ]
        
        conflicts = analyzer.detect_conflicts(results, tolerance=0.01)
        
        assert len(conflicts) == 0
    
    def test_multiple_agents_multiple_conflicts(self):
        """Test multiple agents."""
        analyzer = ConflictAnalyzer()
        
        results = [
            AgentResult("a1", "Agent 1", 1),
            AgentResult("a2", "Agent 2", 2),
            AgentResult("a3", "Agent 3", 1),  # Conflicts with a2
        ]
        
        conflicts = analyzer.detect_conflicts(results)
        
        # a1-a2, a1-a3 same, a2-a3
        assert len(conflicts) > 0
    
    def test_single_agent_no_conflict(self):
        """Test single agent produces no conflicts."""
        analyzer = ConflictAnalyzer()
        
        results = [AgentResult("a1", "Agent 1", 42)]
        
        conflicts = analyzer.detect_conflicts(results)
        
        assert len(conflicts) == 0
    
    def test_empty_results_no_conflict(self):
        """Test empty results."""
        analyzer = ConflictAnalyzer()
        
        conflicts = analyzer.detect_conflicts([])
        
        assert len(conflicts) == 0


class TestConflictResolver:
    """Tests for ConflictResolver."""
    
    def test_initialization(self):
        """Test resolver creation."""
        resolver = ConflictResolver(
            strategy=ConflictResolutionStrategy.PRIORITY_BASED
        )
        
        assert resolver.strategy == ConflictResolutionStrategy.PRIORITY_BASED
    
    def test_resolve_priority_based(self):
        """Test priority-based resolution."""
        resolver = ConflictResolver(strategy=ConflictResolutionStrategy.PRIORITY_BASED)
        
        conflict = Conflict(
            conflict_id="c1",
            conflicting_agents=["a1", "a2"],
            conflicting_values=[1, 2]
        )
        
        results = [
            AgentResult("a1", "Agent 1", 1, priority=5),
            AgentResult("a2", "Agent 2", 2, priority=10),
        ]
        
        resolved = resolver.resolve(conflict, results)
        
        assert resolved.resolved
        assert resolved.resolution == 2  # From higher priority agent
    
    def test_resolve_confidence_based(self):
        """Test confidence-based resolution."""
        resolver = ConflictResolver(strategy=ConflictResolutionStrategy.CONFIDENCE_BASED)
        
        conflict = Conflict(
            conflict_id="c1",
            conflicting_agents=["a1", "a2"],
            conflicting_values=[1, 2]
        )
        
        results = [
            AgentResult("a1", "Agent 1", 1, confidence=0.5),
            AgentResult("a2", "Agent 2", 2, confidence=0.9),
        ]
        
        resolved = resolver.resolve(conflict, results)
        
        assert resolved.resolved
        assert resolved.resolution == 2  # From more confident agent
    
    def test_resolve_voting(self):
        """Test voting-based resolution."""
        resolver = ConflictResolver(strategy=ConflictResolutionStrategy.VOTING)
        
        conflict = Conflict(
            conflict_id="c1",
            conflicting_agents=["a1", "a2", "a3"],
            conflicting_values=[1, 1, 2]
        )
        
        results = [
            AgentResult("a1", "Agent 1", 1),
            AgentResult("a2", "Agent 2", 1),
            AgentResult("a3", "Agent 3", 2),
        ]
        
        resolved = resolver.resolve(conflict, results)
        
        assert resolved.resolved
        assert resolved.resolution == 1  # Majority wins
    
    def test_resolve_merge_dicts(self):
        """Test merge resolution with dicts."""
        resolver = ConflictResolver(strategy=ConflictResolutionStrategy.MERGE)
        
        conflict = Conflict(
            conflict_id="c1",
            conflicting_agents=["a1", "a2"],
            conflicting_values=[{"x": 1}, {"y": 2}]
        )
        
        results = [
            AgentResult("a1", "Agent 1", {"x": 1}),
            AgentResult("a2", "Agent 2", {"y": 2}),
        ]
        
        resolved = resolver.resolve(conflict, results)
        
        assert resolved.resolved
        assert resolved.resolution == {"x": 1, "y": 2}
    
    def test_resolve_merge_non_dicts(self):
        """Test merge with non-dict values doesn't resolve."""
        resolver = ConflictResolver(strategy=ConflictResolutionStrategy.MERGE)
        
        conflict = Conflict(
            conflict_id="c1",
            conflicting_agents=["a1", "a2"],
            conflicting_values=[1, 2]
        )
        
        results = [
            AgentResult("a1", "Agent 1", 1),
            AgentResult("a2", "Agent 2", 2),
        ]
        
        resolved = resolver.resolve(conflict, results)
        
        # Merge doesn't work with non-dicts, so resolution stays None
        assert not resolved.resolved or resolved.resolution is None
    
    def test_custom_resolver(self):
        """Test custom resolver."""
        resolver = ConflictResolver()
        
        def custom_resolver(results):
            # Take average for numeric
            values = [r.value for r in results]
            numeric = [v for v in values if isinstance(v, (int, float))]
            return sum(numeric) / len(numeric) if numeric else None
        
        resolver.register_custom_resolver("average", custom_resolver)
        
        conflict = Conflict(
            conflict_id="c1",
            conflicting_agents=["a1", "a2"],
            conflicting_values=[10, 20]
        )
        
        results = [
            AgentResult("a1", "Agent 1", 10),
            AgentResult("a2", "Agent 2", 20),
        ]
        
        resolved = resolver.resolve(
            conflict,
            results,
            custom_resolver_name="average"
        )
        
        assert resolved.resolved
        assert resolved.resolution == 15.0


class TestConflictResolutionStrategy:
    """Test resolution strategy enums."""
    
    def test_priority_based_enum(self):
        """Test PRIORITY_BASED value."""
        assert ConflictResolutionStrategy.PRIORITY_BASED.value == "priority_based"
    
    def test_confidence_based_enum(self):
        """Test CONFIDENCE_BASED value."""
        assert ConflictResolutionStrategy.CONFIDENCE_BASED.value == "confidence_based"
    
    def test_voting_enum(self):
        """Test VOTING value."""
        assert ConflictResolutionStrategy.VOTING.value == "voting"
    
    def test_merge_enum(self):
        """Test MERGE value."""
        assert ConflictResolutionStrategy.MERGE.value == "merge"


class TestConflictDetectionEdgeCases:
    """Test edge cases in conflict detection."""
    
    def test_string_case_insensitive_same(self):
        """Test string comparison is case-insensitive."""
        analyzer = ConflictAnalyzer()
        
        results = [
            AgentResult("a1", "Agent 1", "Test"),
            AgentResult("a2", "Agent 2", "test"),
        ]
        
        conflicts = analyzer.detect_conflicts(results)
        
        # Case-insensitive comparison means no conflict
        assert len(conflicts) == 0
    
    def test_decimal_numeric_comparison(self):
        """Test decimal comparison."""
        analyzer = ConflictAnalyzer()
        
        results = [
            AgentResult("a1", "Agent 1", 3.14),
            AgentResult("a2", "Agent 2", 3.14),
        ]
        
        conflicts = analyzer.detect_conflicts(results)
        
        assert len(conflicts) == 0
