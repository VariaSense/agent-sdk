"""Tests for result aggregator."""

import pytest
from agent_sdk.coordination.aggregator import (
    AggregationStrategy,
    AggregationResult,
    ResultAggregator
)


class TestAggregationResult:
    """Tests for AggregationResult."""
    
    def test_creation(self):
        """Test result creation."""
        result = AggregationResult(
            aggregated_value=42,
            source_values=[42, 42],
            agreement_score=1.0
        )
        
        assert result.aggregated_value == 42
        assert result.source_values == [42, 42]
        assert result.agreement_score == 1.0
    
    def test_to_dict(self):
        """Test serialization."""
        result = AggregationResult(
            aggregated_value=42,
            source_values=[42, 42],
            strategy_used=AggregationStrategy.FIRST_SUCCESS
        )
        
        d = result.to_dict()
        
        assert d["aggregated_value"] == 42
        assert d["strategy_used"] == "first_success"


class TestResultAggregator:
    """Tests for ResultAggregator."""
    
    def test_initialization(self):
        """Test aggregator creation."""
        agg = ResultAggregator(strategy=AggregationStrategy.FIRST_SUCCESS)
        
        assert agg.strategy == AggregationStrategy.FIRST_SUCCESS
    
    def test_first_success_all_valid(self):
        """Test first success with all values."""
        agg = ResultAggregator()
        result = agg.aggregate([1, 2, 3], strategy=AggregationStrategy.FIRST_SUCCESS)
        
        assert result.aggregated_value == 1
        assert result.strategy_used == AggregationStrategy.FIRST_SUCCESS
    
    def test_first_success_with_none(self):
        """Test first success skips None."""
        agg = ResultAggregator()
        result = agg.aggregate([None, None, 3], strategy=AggregationStrategy.FIRST_SUCCESS)
        
        assert result.aggregated_value == 3
    
    def test_first_success_all_none(self):
        """Test first success with all None."""
        agg = ResultAggregator()
        result = agg.aggregate([None, None], strategy=AggregationStrategy.FIRST_SUCCESS)
        
        assert result.aggregated_value is None
        assert result.agreement_score == 0.0
    
    def test_majority_vote_single(self):
        """Test majority vote."""
        agg = ResultAggregator()
        result = agg.aggregate([1, 1, 1], strategy=AggregationStrategy.MAJORITY_VOTE)
        
        assert result.aggregated_value == 1
        assert result.agreement_score == 1.0
    
    def test_majority_vote_tie(self):
        """Test majority vote with tie."""
        agg = ResultAggregator()
        result = agg.aggregate([1, 2, 1, 2], strategy=AggregationStrategy.MAJORITY_VOTE)
        
        assert result.aggregated_value in [1, 2]
        assert result.agreement_score == 0.5
    
    def test_unanimous_all_same(self):
        """Test unanimous strategy."""
        agg = ResultAggregator()
        result = agg.aggregate([5, 5, 5], strategy=AggregationStrategy.UNANIMOUS)
        
        assert result.aggregated_value == 5
        assert result.confidence == 1.0
    
    def test_unanimous_different(self):
        """Test unanimous with different values."""
        agg = ResultAggregator()
        result = agg.aggregate([5, 5, 6], strategy=AggregationStrategy.UNANIMOUS)
        
        assert result.aggregated_value is None
        assert result.confidence == 0.0
    
    def test_average_numeric(self):
        """Test average with numbers."""
        agg = ResultAggregator()
        result = agg.aggregate([1, 2, 3], strategy=AggregationStrategy.AVERAGE)
        
        assert result.aggregated_value == 2.0
    
    def test_average_floats(self):
        """Test average with floats."""
        agg = ResultAggregator()
        result = agg.aggregate([1.0, 2.0, 3.0], strategy=AggregationStrategy.AVERAGE)
        
        assert result.aggregated_value == 2.0
    
    def test_average_mixed_types(self):
        """Test average with non-numeric values."""
        agg = ResultAggregator()
        result = agg.aggregate([1, "not_numeric", 3], strategy=AggregationStrategy.AVERAGE)
        
        assert result.aggregated_value == 2.0
        assert result.confidence == 2.0 / 3  # 2 numeric out of 3
    
    def test_concat_lists(self):
        """Test concat with lists."""
        agg = ResultAggregator()
        result = agg.aggregate(
            [[1, 2], [3, 4], [5]],
            strategy=AggregationStrategy.CONCAT
        )
        
        assert result.aggregated_value == [1, 2, 3, 4, 5]
    
    def test_concat_mixed(self):
        """Test concat with mixed types."""
        agg = ResultAggregator()
        result = agg.aggregate(
            [[1, 2], 3, [4]],
            strategy=AggregationStrategy.CONCAT
        )
        
        assert result.aggregated_value == [1, 2, 3, 4]
    
    def test_merge_dicts(self):
        """Test merge with dictionaries."""
        agg = ResultAggregator()
        result = agg.aggregate(
            [{"a": 1}, {"b": 2}, {"c": 3}],
            strategy=AggregationStrategy.MERGE
        )
        
        assert result.aggregated_value == {"a": 1, "b": 2, "c": 3}
    
    def test_merge_non_dicts(self):
        """Test merge with non-dict values."""
        agg = ResultAggregator()
        result = agg.aggregate(
            [1, 2, 3],
            strategy=AggregationStrategy.MERGE
        )
        
        assert result.aggregated_value is None
    
    def test_empty_values(self):
        """Test with empty values."""
        agg = ResultAggregator()
        result = agg.aggregate([])
        
        assert result.aggregated_value is None
    
    def test_custom_aggregator(self):
        """Test custom aggregator."""
        agg = ResultAggregator()
        
        def custom_sum(values):
            return sum(v for v in values if isinstance(v, int))
        
        agg.register_custom_aggregator("sum", custom_sum)
        
        result = agg.aggregate(
            [1, 2, 3],
            custom_aggregator_name="sum"
        )
        
        assert result.aggregated_value == 6
        assert result.strategy_used == AggregationStrategy.CUSTOM
    
    def test_custom_aggregator_error_handling(self):
        """Test custom aggregator error handling."""
        agg = ResultAggregator()
        
        def failing_aggregator(values):
            raise ValueError("Test error")
        
        agg.register_custom_aggregator("failing", failing_aggregator)
        
        result = agg.aggregate(
            [1, 2, 3],
            custom_aggregator_name="failing"
        )
        
        assert result.aggregated_value is None
        assert "error" in result.metadata


class TestAggregationStrategies:
    """Test all aggregation strategies."""
    
    def test_first_success_strategy_enum(self):
        """Test FIRST_SUCCESS enum value."""
        assert AggregationStrategy.FIRST_SUCCESS.value == "first_success"
    
    def test_majority_vote_strategy_enum(self):
        """Test MAJORITY_VOTE enum value."""
        assert AggregationStrategy.MAJORITY_VOTE.value == "majority_vote"
    
    def test_unanimous_strategy_enum(self):
        """Test UNANIMOUS enum value."""
        assert AggregationStrategy.UNANIMOUS.value == "unanimous"
    
    def test_average_strategy_enum(self):
        """Test AVERAGE enum value."""
        assert AggregationStrategy.AVERAGE.value == "average"
    
    def test_concat_strategy_enum(self):
        """Test CONCAT enum value."""
        assert AggregationStrategy.CONCAT.value == "concat"
    
    def test_merge_strategy_enum(self):
        """Test MERGE enum value."""
        assert AggregationStrategy.MERGE.value == "merge"
    
    def test_custom_strategy_enum(self):
        """Test CUSTOM enum value."""
        assert AggregationStrategy.CUSTOM.value == "custom"


class TestAggregationEdgeCases:
    """Test edge cases."""
    
    def test_single_value_first_success(self):
        """Test single value with first success."""
        agg = ResultAggregator()
        result = agg.aggregate([42], strategy=AggregationStrategy.FIRST_SUCCESS)
        
        assert result.aggregated_value == 42
    
    def test_average_zero_values(self):
        """Test average with zero."""
        agg = ResultAggregator()
        result = agg.aggregate([0, 0, 0], strategy=AggregationStrategy.AVERAGE)
        
        assert result.aggregated_value == 0.0
    
    def test_merge_overlapping_keys(self):
        """Test merge with overlapping keys."""
        agg = ResultAggregator()
        result = agg.aggregate(
            [{"a": 1}, {"a": 2}, {"a": 3}],
            strategy=AggregationStrategy.MERGE
        )
        
        # Last one wins in dict update
        assert result.aggregated_value == {"a": 3}
