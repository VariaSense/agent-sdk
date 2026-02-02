"""Tests for OpenTelemetry integration."""

import pytest
from datetime import datetime
from agent_sdk.observability.otel import (
    SpanKind,
    SpanStatus,
    Span,
    Metric,
    CostMetric,
    TracingProvider,
    MetricsCollector,
    ObservabilityManager,
    create_observability_manager,
)


class TestSpan:
    """Test Span functionality."""

    def test_create_span(self):
        """Test creating a span."""
        span = Span(
            name="test_operation",
            span_id="span123",
            trace_id="trace456",
        )
        assert span.name == "test_operation"
        assert span.span_id == "span123"
        assert span.trace_id == "trace456"

    def test_span_add_attribute(self):
        """Test adding attributes to span."""
        span = Span(name="test", span_id="1", trace_id="2")
        span.add_attribute("key", "value")
        assert span.attributes["key"] == "value"

    def test_span_add_event(self):
        """Test adding events to span."""
        span = Span(name="test", span_id="1", trace_id="2")
        span.add_event("event1", {"data": "info"})
        assert len(span.events) == 1
        assert span.events[0].name == "event1"

    def test_span_duration(self):
        """Test span duration calculation."""
        span = Span(name="test", span_id="1", trace_id="2")
        span.end()
        assert span.duration_ms() >= 0

    def test_span_error(self):
        """Test marking span as error."""
        span = Span(name="test", span_id="1", trace_id="2")
        span.set_error("Something went wrong")
        assert span.status == SpanStatus.ERROR
        assert span.error_message == "Something went wrong"

    def test_span_to_dict(self):
        """Test converting span to dict."""
        span = Span(name="test", span_id="1", trace_id="2")
        span.add_attribute("key", "value")
        span.end()
        span_dict = span.to_dict()
        assert span_dict["name"] == "test"
        assert span_dict["span_id"] == "1"
        assert span_dict["attributes"]["key"] == "value"


class TestTracingProvider:
    """Test TracingProvider functionality."""

    def test_start_span(self):
        """Test starting a span."""
        provider = TracingProvider("test-service")
        span = provider.start_span("operation")
        assert span is not None
        assert span.name == "operation"

    def test_trace_context_manager(self):
        """Test using trace as context manager."""
        provider = TracingProvider()
        with provider.trace("test_op") as span:
            assert span.status == SpanStatus.UNSET
        assert span.status == SpanStatus.OK

    def test_span_parent_child(self):
        """Test parent-child span relationship."""
        provider = TracingProvider()
        parent = provider.start_span("parent")
        child = provider.start_span("child")
        assert child.parent_span_id == parent.span_id

    def test_get_trace(self):
        """Test retrieving trace by ID."""
        provider = TracingProvider()
        span1 = provider.start_span("op1")
        span2 = provider.start_span("op2")
        trace_id = span1.trace_id
        trace_spans = provider.get_trace(trace_id)
        assert len(trace_spans) >= 1

    def test_trace_error_handling(self):
        """Test trace error handling."""
        provider = TracingProvider()
        try:
            with provider.trace("failing_op"):
                raise ValueError("Test error")
        except ValueError:
            pass
        # Find span and verify error
        spans = list(provider.spans.values())
        assert any(s.status == SpanStatus.ERROR for s in spans)


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def test_record_metric(self):
        """Test recording a metric."""
        collector = MetricsCollector()
        collector.record_metric("test_metric", 42.0, unit="count")
        assert len(collector.metrics) == 1
        assert collector.metrics[0].value == 42.0

    def test_record_latency(self):
        """Test recording latency metrics."""
        collector = MetricsCollector()
        collector.record_latency("operation", 100.5)
        assert len(collector.metrics) == 1
        assert "operation" in collector.latency_samples

    def test_record_cost(self):
        """Test recording cost metrics."""
        collector = MetricsCollector()
        collector.record_cost("gpt-4", "openai", 100, 50, 0.003)
        assert len(collector.cost_metrics) == 1
        assert collector.cost_metrics[0].cost_usd == 0.003

    def test_get_statistics(self):
        """Test getting statistics."""
        collector = MetricsCollector()
        collector.record_latency("op1", 100)
        collector.record_latency("op1", 200)
        collector.record_cost("model1", "provider1", 100, 50, 0.05)

        stats = collector.get_statistics()
        assert stats["metric_count"] >= 2
        assert stats["cost_count"] == 1
        assert stats["total_cost_usd"] == 0.05
        assert "op1" in stats["latency_statistics"]

    def test_latency_statistics(self):
        """Test latency statistics calculation."""
        collector = MetricsCollector()
        for latency in [100, 200, 150, 300, 120]:
            collector.record_latency("operation", latency)

        stats = collector.get_statistics()
        op_stats = stats["latency_statistics"]["operation"]
        assert op_stats["count"] == 5
        assert op_stats["min_ms"] == 100
        assert op_stats["max_ms"] == 300


class TestCostMetric:
    """Test CostMetric."""

    def test_cost_metric_creation(self):
        """Test creating cost metric."""
        metric = CostMetric(
            model="gpt-4",
            provider="openai",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.03,
        )
        assert metric.model == "gpt-4"
        assert metric.input_tokens == 1000
        assert metric.cost_usd == 0.03

    def test_cost_metric_to_dict(self):
        """Test converting cost metric to dict."""
        metric = CostMetric(
            model="claude-3",
            provider="anthropic",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.01,
        )
        metric_dict = metric.to_dict()
        assert metric_dict["model"] == "claude-3"
        assert metric_dict["provider"] == "anthropic"


class TestObservabilityManager:
    """Test ObservabilityManager."""

    def test_create_manager(self):
        """Test creating observability manager."""
        manager = create_observability_manager("test-service")
        assert manager is not None
        assert manager.service_name == "test-service"

    def test_trace_agent_execution(self):
        """Test tracing agent execution."""
        manager = create_observability_manager()
        with manager.trace_agent_execution("agent1", "solve_problem"):
            pass
        traces = manager.tracer.spans
        assert len(traces) > 0

    def test_trace_tool_call(self):
        """Test tracing tool call."""
        manager = create_observability_manager()
        with manager.trace_tool_call("calculator", {"expr": "2+2"}):
            pass
        assert len(manager.tracer.spans) > 0

    def test_trace_model_call(self):
        """Test tracing model call."""
        manager = create_observability_manager()
        with manager.trace_model_call("gpt-4", "openai"):
            pass
        assert len(manager.tracer.spans) > 0

    def test_record_tool_execution(self):
        """Test recording tool execution."""
        manager = create_observability_manager()
        manager.record_tool_execution("search", 150.5, True)
        stats = manager.metrics.get_statistics()
        assert stats["metric_count"] > 0

    def test_record_model_execution(self):
        """Test recording model execution."""
        manager = create_observability_manager()
        manager.record_model_execution(
            "gpt-4", "openai", 200.0, 1000, 500, 0.03
        )
        stats = manager.metrics.get_statistics()
        assert stats["cost_count"] == 1
        assert stats["total_cost_usd"] == 0.03

    def test_get_summary(self):
        """Test getting observability summary."""
        manager = create_observability_manager("test-service")
        manager.record_tool_execution("tool1", 100, True)
        summary = manager.get_summary()
        assert summary["service"] == "test-service"
        assert "tracing" in summary
        assert "metrics" in summary

    def test_export_json(self):
        """Test exporting as JSON."""
        manager = create_observability_manager()
        manager.record_metric("test", 42)
        json_str = manager.export_json()
        assert "service" in json_str
        assert "test" in json_str
