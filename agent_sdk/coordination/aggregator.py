"""Result aggregation from multiple agents."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class AggregationStrategy(Enum):
    """Strategies for aggregating results from multiple agents."""
    
    FIRST_SUCCESS = "first_success"    # Return first successful result
    MAJORITY_VOTE = "majority_vote"   # Return majority result
    UNANIMOUS = "unanimous"            # Require all agents to agree
    AVERAGE = "average"               # Average numeric results
    CONCAT = "concat"                 # Concatenate all results
    MERGE = "merge"                   # Merge dictionaries
    CUSTOM = "custom"                 # Custom aggregation function


@dataclass
class AggregationResult:
    """Result of aggregation."""
    
    aggregated_value: Any = None
    source_values: List[Any] = field(default_factory=list)
    strategy_used: AggregationStrategy = AggregationStrategy.FIRST_SUCCESS
    agreement_score: float = 0.0  # 0.0-1.0, how much agents agreed
    confidence: float = 1.0  # Confidence in result
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "aggregated_value": self.aggregated_value,
            "source_values": self.source_values,
            "strategy_used": self.strategy_used.value,
            "agreement_score": self.agreement_score,
            "confidence": self.confidence,
            "metadata": self.metadata
        }


class ResultAggregator:
    """Aggregates results from multiple agent executions."""
    
    def __init__(self, strategy: AggregationStrategy = AggregationStrategy.FIRST_SUCCESS):
        """Initialize aggregator.
        
        Args:
            strategy: Default aggregation strategy
        """
        self.strategy = strategy
        self.custom_aggregators: Dict[str, Callable] = {}
    
    def register_custom_aggregator(
        self,
        name: str,
        aggregator_fn: Callable[[List[Any]], Any]
    ) -> None:
        """Register custom aggregation function.
        
        Args:
            name: Name of aggregator
            aggregator_fn: Function that aggregates values
        """
        self.custom_aggregators[name] = aggregator_fn
    
    def aggregate(
        self,
        values: List[Any],
        strategy: Optional[AggregationStrategy] = None,
        custom_aggregator_name: Optional[str] = None
    ) -> AggregationResult:
        """Aggregate multiple values.
        
        Args:
            values: Values to aggregate
            strategy: Aggregation strategy (uses default if None)
            custom_aggregator_name: Name of custom aggregator
        
        Returns:
            Aggregation result
        """
        if not values:
            return AggregationResult(
                aggregated_value=None,
                source_values=values,
                agreement_score=0.0
            )
        
        if custom_aggregator_name and custom_aggregator_name in self.custom_aggregators:
            return self._aggregate_custom(
                values,
                custom_aggregator_name
            )
        
        strategy = strategy or self.strategy
        
        if strategy == AggregationStrategy.FIRST_SUCCESS:
            return self._aggregate_first_success(values)
        elif strategy == AggregationStrategy.MAJORITY_VOTE:
            return self._aggregate_majority_vote(values)
        elif strategy == AggregationStrategy.UNANIMOUS:
            return self._aggregate_unanimous(values)
        elif strategy == AggregationStrategy.AVERAGE:
            return self._aggregate_average(values)
        elif strategy == AggregationStrategy.CONCAT:
            return self._aggregate_concat(values)
        elif strategy == AggregationStrategy.MERGE:
            return self._aggregate_merge(values)
        else:
            return AggregationResult(aggregated_value=None)
    
    def _aggregate_first_success(self, values: List[Any]) -> AggregationResult:
        """Return first non-None value."""
        for value in values:
            if value is not None:
                return AggregationResult(
                    aggregated_value=value,
                    source_values=values,
                    strategy_used=AggregationStrategy.FIRST_SUCCESS,
                    agreement_score=1.0 / len(values),
                    confidence=1.0
                )
        return AggregationResult(
            aggregated_value=None,
            source_values=values,
            strategy_used=AggregationStrategy.FIRST_SUCCESS,
            agreement_score=0.0
        )
    
    def _aggregate_majority_vote(self, values: List[Any]) -> AggregationResult:
        """Return value with most votes."""
        if not values:
            return AggregationResult(aggregated_value=None)
        
        # Count occurrences
        vote_counts = {}
        for value in values:
            key = str(value)  # Use string representation for comparison
            vote_counts[key] = vote_counts.get(key, 0) + 1
        
        # Get majority
        max_votes = max(vote_counts.values())
        majority_value = [v for v in values if str(v) in vote_counts and vote_counts[str(v)] == max_votes][0]
        agreement_score = max_votes / len(values)
        
        return AggregationResult(
            aggregated_value=majority_value,
            source_values=values,
            strategy_used=AggregationStrategy.MAJORITY_VOTE,
            agreement_score=agreement_score,
            confidence=agreement_score
        )
    
    def _aggregate_unanimous(self, values: List[Any]) -> AggregationResult:
        """All values must be the same."""
        if not values:
            return AggregationResult(aggregated_value=None)
        
        first_value = values[0]
        all_same = all(v == first_value for v in values)
        
        return AggregationResult(
            aggregated_value=first_value if all_same else None,
            source_values=values,
            strategy_used=AggregationStrategy.UNANIMOUS,
            agreement_score=1.0 if all_same else 0.0,
            confidence=1.0 if all_same else 0.0
        )
    
    def _aggregate_average(self, values: List[Any]) -> AggregationResult:
        """Average numeric values."""
        numeric_values = []
        for value in values:
            try:
                numeric_values.append(float(value))
            except (TypeError, ValueError):
                pass
        
        if not numeric_values:
            return AggregationResult(aggregated_value=None, source_values=values)
        
        average = sum(numeric_values) / len(numeric_values)
        
        return AggregationResult(
            aggregated_value=average,
            source_values=values,
            strategy_used=AggregationStrategy.AVERAGE,
            agreement_score=1.0,
            confidence=len(numeric_values) / len(values) if values else 0.0
        )
    
    def _aggregate_concat(self, values: List[Any]) -> AggregationResult:
        """Concatenate results."""
        result = []
        for value in values:
            if isinstance(value, list):
                result.extend(value)
            else:
                result.append(value)
        
        return AggregationResult(
            aggregated_value=result,
            source_values=values,
            strategy_used=AggregationStrategy.CONCAT,
            agreement_score=1.0,
            confidence=1.0
        )
    
    def _aggregate_merge(self, values: List[Any]) -> AggregationResult:
        """Merge dictionary results."""
        merged = {}
        for value in values:
            if isinstance(value, dict):
                merged.update(value)
        
        return AggregationResult(
            aggregated_value=merged if merged else None,
            source_values=values,
            strategy_used=AggregationStrategy.MERGE,
            agreement_score=1.0,
            confidence=1.0 if merged else 0.0
        )
    
    def _aggregate_custom(
        self,
        values: List[Any],
        aggregator_name: str
    ) -> AggregationResult:
        """Apply custom aggregation."""
        try:
            aggregator_fn = self.custom_aggregators[aggregator_name]
            result = aggregator_fn(values)
            
            return AggregationResult(
                aggregated_value=result,
                source_values=values,
                strategy_used=AggregationStrategy.CUSTOM,
                confidence=1.0,
                metadata={"custom_aggregator": aggregator_name}
            )
        except Exception as e:
            return AggregationResult(
                aggregated_value=None,
                source_values=values,
                metadata={"error": str(e)}
            )
