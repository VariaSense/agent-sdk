"""Tests for routing metrics and analytics."""

import pytest
from datetime import datetime
from agent_sdk.routing.metrics import RoutingMetrics, RoutingAnalytics


class TestRoutingMetrics:
    """Test RoutingMetrics dataclass."""
    
    def test_routing_metrics_creation(self):
        """Test basic RoutingMetrics creation."""
        metrics = RoutingMetrics(
            decision_time_ms=45.5,
            paths_evaluated=3,
            conditions_checked=5,
            confidence_score=0.92,
            strategy_used="parallel",
            total_tokens_estimated=250,
            estimated_cost=0.05
        )
        
        assert metrics.decision_time_ms == 45.5
        assert metrics.paths_evaluated == 3
        assert metrics.conditions_checked == 5
        assert metrics.confidence_score == 0.92
        assert metrics.strategy_used == "parallel"
    
    def test_routing_metrics_defaults(self):
        """Test RoutingMetrics default values."""
        metrics = RoutingMetrics(
            decision_time_ms=50.0,
            paths_evaluated=2,
            conditions_checked=3,
            confidence_score=0.8,
            strategy_used="direct",
            total_tokens_estimated=100,
            estimated_cost=0.01
        )
        
        assert metrics.success is True
        assert metrics.metadata == {}
        assert isinstance(metrics.timestamp, datetime)
    
    def test_routing_metrics_success_tracking(self):
        """Test success/failure tracking."""
        success_metrics = RoutingMetrics(
            decision_time_ms=100.0,
            paths_evaluated=1,
            conditions_checked=2,
            confidence_score=0.95,
            strategy_used="direct",
            total_tokens_estimated=50,
            estimated_cost=0.01,
            success=True
        )
        
        failed_metrics = RoutingMetrics(
            decision_time_ms=200.0,
            paths_evaluated=3,
            conditions_checked=5,
            confidence_score=0.5,
            strategy_used="sequential",
            total_tokens_estimated=500,
            estimated_cost=0.1,
            success=False
        )
        
        assert success_metrics.success is True
        assert failed_metrics.success is False
    
    def test_routing_metrics_cost_tracking(self):
        """Test cost tracking."""
        metrics = RoutingMetrics(
            decision_time_ms=50.0,
            paths_evaluated=1,
            conditions_checked=1,
            confidence_score=0.9,
            strategy_used="direct",
            total_tokens_estimated=100,
            estimated_cost=0.0234
        )
        
        assert metrics.estimated_cost == 0.0234
    
    def test_routing_metrics_strategy_info(self):
        """Test strategy information in metrics."""
        metrics = RoutingMetrics(
            decision_time_ms=50.0,
            paths_evaluated=2,
            conditions_checked=3,
            confidence_score=0.8,
            strategy_used="parallel",
            total_tokens_estimated=200,
            estimated_cost=0.02
        )
        
        assert metrics.strategy_used == "parallel"
    
    def test_routing_metrics_to_dict(self):
        """Test RoutingMetrics conversion to dict."""
        metrics = RoutingMetrics(
            decision_time_ms=50.0,
            paths_evaluated=2,
            conditions_checked=3,
            confidence_score=0.85,
            strategy_used="direct",
            total_tokens_estimated=150,
            estimated_cost=0.01,
            success=True
        )
        
        metrics_dict = metrics.to_dict()
        assert metrics_dict["decision_time_ms"] == 50.0
        assert metrics_dict["paths_evaluated"] == 2
        assert metrics_dict["conditions_checked"] == 3
        assert metrics_dict["confidence_score"] == 0.85
        assert metrics_dict["strategy_used"] == "direct"
        assert metrics_dict["success"] is True
    
    def test_routing_metrics_timestamp(self):
        """Test timestamp is recorded."""
        metrics = RoutingMetrics(
            decision_time_ms=50.0,
            paths_evaluated=1,
            conditions_checked=1,
            confidence_score=0.9,
            strategy_used="direct",
            total_tokens_estimated=100,
            estimated_cost=0.01
        )
        
        assert hasattr(metrics, "timestamp")
        assert isinstance(metrics.timestamp, datetime)


class TestRoutingAnalytics:
    """Test RoutingAnalytics class."""
    
    def test_routing_analytics_creation(self):
        """Test basic RoutingAnalytics creation."""
        analytics = RoutingAnalytics()
        
        assert isinstance(analytics, RoutingAnalytics)
        assert len(analytics.decisions) == 0
        assert len(analytics.path_stats) == 0
        assert len(analytics.strategy_stats) == 0
    
    def test_record_decision_single(self):
        """Test recording a single decision."""
        analytics = RoutingAnalytics()
        metrics = RoutingMetrics(
            decision_time_ms=50.0,
            paths_evaluated=2,
            conditions_checked=3,
            confidence_score=0.85,
            strategy_used="direct",
            total_tokens_estimated=100,
            estimated_cost=0.01
        )
        
        analytics.record_decision("path1", metrics)
        
        assert len(analytics.decisions) == 1
        assert "path1" in analytics.path_stats
    
    def test_record_multiple_decisions(self):
        """Test recording multiple decisions."""
        analytics = RoutingAnalytics()
        
        for i in range(3):
            metrics = RoutingMetrics(
                decision_time_ms=50.0 + i * 10,
                paths_evaluated=i + 1,
                conditions_checked=i + 2,
                confidence_score=0.8 + i * 0.05,
                strategy_used="direct" if i % 2 == 0 else "parallel",
                total_tokens_estimated=100 + i * 50,
                estimated_cost=0.01 * (i + 1)
            )
            analytics.record_decision(f"path{i}", metrics)
        
        assert len(analytics.decisions) == 3
        assert len(analytics.path_stats) == 3
    
    def test_get_path_success_rates(self):
        """Test retrieving success rates per path."""
        analytics = RoutingAnalytics()
        
        # Path 1: 2 successes, 1 failure
        for i in range(3):
            metrics = RoutingMetrics(
                decision_time_ms=50.0,
                paths_evaluated=1,
                conditions_checked=1,
                confidence_score=0.8,
                strategy_used="direct",
                total_tokens_estimated=100,
                estimated_cost=0.01,
                success=(i < 2)
            )
            analytics.record_decision("path1", metrics)
        
        # Path 2: all successes
        for i in range(2):
            metrics = RoutingMetrics(
                decision_time_ms=50.0,
                paths_evaluated=1,
                conditions_checked=1,
                confidence_score=0.9,
                strategy_used="parallel",
                total_tokens_estimated=150,
                estimated_cost=0.02,
                success=True
            )
            analytics.record_decision("path2", metrics)
        
        rates = analytics.get_path_success_rates()
        
        assert "path1" in rates
        assert "path2" in rates
        assert rates["path1"] == pytest.approx(2/3, rel=0.01)
        assert rates["path2"] == 1.0
    
    def test_path_statistics_updated(self):
        """Test that path statistics are updated correctly."""
        analytics = RoutingAnalytics()
        
        metrics1 = RoutingMetrics(
            decision_time_ms=100.0,
            paths_evaluated=1,
            conditions_checked=1,
            confidence_score=0.9,
            strategy_used="direct",
            total_tokens_estimated=200,
            estimated_cost=0.02,
            success=True
        )
        
        metrics2 = RoutingMetrics(
            decision_time_ms=50.0,
            paths_evaluated=2,
            conditions_checked=2,
            confidence_score=0.8,
            strategy_used="direct",
            total_tokens_estimated=150,
            estimated_cost=0.01,
            success=True
        )
        
        analytics.record_decision("path1", metrics1)
        analytics.record_decision("path1", metrics2)
        
        path_stats = analytics.path_stats["path1"]
        assert path_stats["count"] == 2
        assert path_stats["success_count"] == 2
        assert path_stats["total_cost"] == pytest.approx(0.03, rel=0.001)
        assert path_stats["total_tokens"] == 350
    
    def test_strategy_statistics_tracked(self):
        """Test that strategy statistics are tracked."""
        analytics = RoutingAnalytics()
        
        for strategy in ["direct", "direct", "parallel"]:
            metrics = RoutingMetrics(
                decision_time_ms=50.0,
                paths_evaluated=1,
                conditions_checked=1,
                confidence_score=0.85,
                strategy_used=strategy,
                total_tokens_estimated=100,
                estimated_cost=0.01,
                success=True
            )
            analytics.record_decision("path", metrics)
        
        assert analytics.strategy_stats["direct"]["count"] == 2
        assert analytics.strategy_stats["parallel"]["count"] == 1
        assert analytics.strategy_stats["direct"]["success_count"] == 2
    
    def test_running_averages_calculated(self):
        """Test that running averages are calculated correctly."""
        analytics = RoutingAnalytics()
        
        metrics1 = RoutingMetrics(
            decision_time_ms=100.0,
            paths_evaluated=1,
            conditions_checked=1,
            confidence_score=0.9,
            strategy_used="direct",
            total_tokens_estimated=100,
            estimated_cost=0.01,
            success=True
        )
        
        metrics2 = RoutingMetrics(
            decision_time_ms=50.0,
            paths_evaluated=1,
            conditions_checked=1,
            confidence_score=0.8,
            strategy_used="direct",
            total_tokens_estimated=100,
            estimated_cost=0.01,
            success=True
        )
        
        analytics.record_decision("path1", metrics1)
        path_stats_after_1 = analytics.path_stats["path1"].copy()
        
        analytics.record_decision("path1", metrics2)
        path_stats_after_2 = analytics.path_stats["path1"]
        
        # Average decision time should be 75ms
        assert path_stats_after_2["avg_decision_time_ms"] == pytest.approx(75.0, rel=0.01)
        # Average confidence should be 0.85
        assert path_stats_after_2["avg_confidence"] == pytest.approx(0.85, rel=0.01)
    
    def test_failed_decisions_tracked(self):
        """Test that failed decisions are tracked."""
        analytics = RoutingAnalytics()
        
        success_metrics = RoutingMetrics(
            decision_time_ms=50.0,
            paths_evaluated=1,
            conditions_checked=1,
            confidence_score=0.9,
            strategy_used="direct",
            total_tokens_estimated=100,
            estimated_cost=0.01,
            success=True
        )
        
        failed_metrics = RoutingMetrics(
            decision_time_ms=100.0,
            paths_evaluated=2,
            conditions_checked=2,
            confidence_score=0.5,
            strategy_used="sequential",
            total_tokens_estimated=500,
            estimated_cost=0.05,
            success=False
        )
        
        analytics.record_decision("path1", success_metrics)
        analytics.record_decision("path2", failed_metrics)
        
        path1_stats = analytics.path_stats["path1"]
        path2_stats = analytics.path_stats["path2"]
        
        assert path1_stats["success_count"] == 1
        assert path2_stats["success_count"] == 0
