"""
Tests for metrics collection module.
"""

import pytest
from datetime import datetime
from agent_sdk.observability.metrics import (
    MetricsCollector,
    MetricType,
    MetricData,
    Measurement,
    PerformanceMetrics,
    OperationMetrics,
    OperationMetricsTracker
)


class TestMeasurement:
    """Test Measurement class."""
    
    def test_create_measurement(self):
        """Test creating measurement."""
        ts = datetime.now()
        measurement = Measurement(timestamp=ts, value=42.0, unit="ms")
        assert measurement.value == 42.0
        assert measurement.unit == "ms"
    
    def test_measurement_with_labels(self):
        """Test measurement with labels."""
        measurement = Measurement(
            timestamp=datetime.now(),
            value=42.0,
            labels={"operation": "search", "status": "success"}
        )
        assert measurement.labels["operation"] == "search"
    
    def test_measurement_to_dict(self):
        """Test measurement serialization."""
        measurement = Measurement(
            timestamp=datetime.now(),
            value=42.0,
            unit="ms"
        )
        data = measurement.to_dict()
        assert data["value"] == 42.0
        assert data["unit"] == "ms"


class TestMetricData:
    """Test MetricData class."""
    
    def test_create_metric(self):
        """Test creating metric."""
        metric = MetricData(
            name="request_latency",
            metric_type=MetricType.HISTOGRAM,
            unit="ms"
        )
        assert metric.name == "request_latency"
        assert metric.metric_type == MetricType.HISTOGRAM
    
    def test_add_measurement(self):
        """Test adding measurements."""
        metric = MetricData(
            name="request_latency",
            metric_type=MetricType.HISTOGRAM,
            unit="ms"
        )
        metric.add_measurement(100.0)
        metric.add_measurement(200.0)
        assert metric.get_count() == 2
    
    def test_get_statistics(self):
        """Test getting metric statistics."""
        metric = MetricData(
            name="request_latency",
            metric_type=MetricType.HISTOGRAM,
            unit="ms"
        )
        for value in [100, 200, 150, 300, 250]:
            metric.add_measurement(float(value))
        
        assert metric.get_count() == 5
        assert metric.get_sum() == 1000
        assert metric.get_average() == 200
        assert metric.get_min() == 100
        assert metric.get_max() == 300
    
    def test_percentiles(self):
        """Test percentile calculation."""
        metric = MetricData(
            name="latency",
            metric_type=MetricType.HISTOGRAM
        )
        for i in range(1, 101):
            metric.add_measurement(float(i))
        
        p50 = metric.get_percentile(50)
        p99 = metric.get_percentile(99)
        assert p50 is not None
        assert p99 is not None
        assert p99 >= p50


class TestMetricsCollector:
    """Test MetricsCollector class."""
    
    def test_register_metric(self):
        """Test registering metric."""
        collector = MetricsCollector()
        metric = collector.register_metric(
            "latency",
            MetricType.HISTOGRAM,
            unit="ms"
        )
        assert metric.name == "latency"
    
    def test_record_metric(self):
        """Test recording metric."""
        collector = MetricsCollector()
        collector.register_metric("latency", MetricType.HISTOGRAM, unit="ms")
        collector.record_metric("latency", 100.0)
        
        metric = collector.get_metric("latency")
        assert metric.get_count() == 1
    
    def test_record_metric_not_registered(self):
        """Test recording unregistered metric."""
        collector = MetricsCollector()
        with pytest.raises(ValueError):
            collector.record_metric("unregistered", 100.0)
    
    def test_record_metric_with_labels(self):
        """Test recording metric with labels."""
        collector = MetricsCollector()
        collector.register_metric("request_count", MetricType.COUNTER)
        collector.record_metric(
            "request_count",
            1.0,
            labels={"endpoint": "/api/search", "status": "200"}
        )
        
        metric = collector.get_metric("request_count")
        assert len(metric.measurements) == 1
        assert metric.measurements[0].labels["endpoint"] == "/api/search"
    
    def test_get_summary(self):
        """Test getting metrics summary."""
        collector = MetricsCollector()
        
        # Register and record multiple metrics
        collector.register_metric("latency", MetricType.HISTOGRAM, unit="ms")
        collector.register_metric("throughput", MetricType.GAUGE, unit="ops/sec")
        
        for i in range(5):
            collector.record_metric("latency", 100.0 + i * 10)
            collector.record_metric("throughput", 1000.0)
        
        summary = collector.get_summary()
        assert len(summary) == 2
        assert "latency" in summary
        assert "throughput" in summary
    
    def test_clear_metrics(self):
        """Test clearing metrics."""
        collector = MetricsCollector()
        collector.register_metric("latency", MetricType.HISTOGRAM)
        collector.record_metric("latency", 100.0)
        
        assert len(collector.metrics) == 1
        collector.clear()
        assert len(collector.metrics) == 0


class TestPerformanceMetrics:
    """Test PerformanceMetrics class."""
    
    def test_create_performance_metrics(self):
        """Test creating performance metrics."""
        metrics = PerformanceMetrics(
            operation_name="search",
            start_time=datetime.now()
        )
        assert metrics.operation_name == "search"
        assert metrics.success is True
    
    def test_mark_complete(self):
        """Test marking operation complete."""
        from datetime import timedelta
        start = datetime.now()
        metrics = PerformanceMetrics(
            operation_name="search",
            start_time=start
        )
        
        end = start + timedelta(milliseconds=100)
        metrics.mark_complete(end)
        
        assert metrics.duration_ms == pytest.approx(100.0, abs=1.0)
    
    def test_tokens_per_second(self):
        """Test tokens per second calculation."""
        from datetime import timedelta
        start = datetime.now()
        metrics = PerformanceMetrics(
            operation_name="completion",
            start_time=start,
            token_count=100
        )
        
        end = start + timedelta(milliseconds=1000)  # 1 second
        metrics.mark_complete(end)
        
        assert metrics.tokens_per_second == pytest.approx(100.0)


class TestOperationMetrics:
    """Test OperationMetrics class."""
    
    def test_create_operation_metrics(self):
        """Test creating operation metrics."""
        metrics = OperationMetrics(operation_type="api_call")
        assert metrics.operation_type == "api_call"
        assert metrics.total_operations == 0
    
    def test_add_operation_success(self):
        """Test adding successful operation."""
        metrics = OperationMetrics(operation_type="api_call")
        metrics.add_operation(duration_ms=100.0, token_count=50, success=True)
        
        assert metrics.total_operations == 1
        assert metrics.successful_operations == 1
        assert metrics.failed_operations == 0
    
    def test_add_operation_failure(self):
        """Test adding failed operation."""
        metrics = OperationMetrics(operation_type="api_call")
        metrics.add_operation(duration_ms=100.0, token_count=0, success=False)
        
        assert metrics.total_operations == 1
        assert metrics.successful_operations == 0
        assert metrics.failed_operations == 1
    
    def test_success_rate(self):
        """Test success rate calculation."""
        metrics = OperationMetrics(operation_type="api_call")
        metrics.add_operation(100.0, 50, True)
        metrics.add_operation(150.0, 50, True)
        metrics.add_operation(120.0, 0, False)
        
        assert metrics.success_rate == pytest.approx(2/3)
        assert metrics.failure_rate == pytest.approx(1/3)
    
    def test_average_latency(self):
        """Test average latency calculation."""
        metrics = OperationMetrics(operation_type="api_call")
        metrics.add_operation(100.0, 50, True)
        metrics.add_operation(200.0, 50, True)
        
        assert metrics.average_latency_ms == 150.0
    
    def test_percentile_latency(self):
        """Test percentile latency calculation."""
        metrics = OperationMetrics(operation_type="api_call")
        for i in range(1, 101):
            metrics.add_operation(float(i) * 10, 50, True)
        
        p99 = metrics.p99_latency_ms
        assert p99 is not None
        assert p99 >= metrics.average_latency_ms
    
    def test_throughput(self):
        """Test throughput calculation."""
        metrics = OperationMetrics(operation_type="api_call")
        # 10 operations, each 100ms = 1000ms total
        for _ in range(10):
            metrics.add_operation(100.0, 50, True)
        
        throughput = metrics.throughput_ops_per_second
        assert throughput == pytest.approx(10.0)


class TestOperationMetricsTracker:
    """Test OperationMetricsTracker class."""
    
    def test_create_tracker(self):
        """Test creating tracker."""
        tracker = OperationMetricsTracker()
        assert len(tracker.metrics) == 0
    
    def test_record_operation(self):
        """Test recording operation."""
        tracker = OperationMetricsTracker()
        tracker.record_operation("api_call", 100.0, 50, True)
        
        assert "api_call" in tracker.metrics
        assert tracker.metrics["api_call"].total_operations == 1
    
    def test_get_operation_metrics(self):
        """Test getting operation metrics."""
        tracker = OperationMetricsTracker()
        tracker.record_operation("api_call", 100.0, 50, True)
        tracker.record_operation("api_call", 150.0, 50, True)
        
        metrics = tracker.get_operation_metrics("api_call")
        assert metrics.total_operations == 2
    
    def test_multiple_operation_types(self):
        """Test tracking multiple operation types."""
        tracker = OperationMetricsTracker()
        tracker.record_operation("api_call", 100.0, 50, True)
        tracker.record_operation("db_query", 50.0, 0, True)
        
        assert len(tracker.metrics) == 2
        assert tracker.metrics["api_call"].total_operations == 1
        assert tracker.metrics["db_query"].total_operations == 1
    
    def test_get_summary(self):
        """Test getting summary."""
        tracker = OperationMetricsTracker()
        tracker.record_operation("api_call", 100.0, 50, True)
        tracker.record_operation("db_query", 50.0, 0, True)
        
        summary = tracker.get_summary()
        assert len(summary) == 2
        assert "api_call" in summary
        assert "db_query" in summary


class TestMetricsIntegration:
    """Integration tests for metrics."""
    
    def test_track_agent_execution_metrics(self):
        """Test tracking metrics for agent execution."""
        collector = MetricsCollector()
        tracker = OperationMetricsTracker()
        
        # Register metrics
        collector.register_metric("agent_latency", MetricType.HISTOGRAM, "ms")
        collector.register_metric("tokens_used", MetricType.COUNTER, "tokens")
        
        # Simulate agent execution
        for i in range(5):
            latency = 100.0 + i * 20
            tokens = 150 + i * 10
            
            collector.record_metric("agent_latency", latency)
            collector.record_metric("tokens_used", float(tokens))
            tracker.record_operation("agent_execution", latency, tokens, True)
        
        # Verify metrics
        latency_metric = collector.get_metric("agent_latency")
        assert latency_metric.get_count() == 5
        assert latency_metric.get_max() >= latency_metric.get_min()
        
        exec_metrics = tracker.get_operation_metrics("agent_execution")
        assert exec_metrics.total_operations == 5
