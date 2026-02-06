"""Tests for observability metrics pipeline."""

from agent_sdk.observability.events import ObsEvent
from agent_sdk.observability.metrics import MetricsCollector
from agent_sdk.observability.metrics_pipeline import ObsMetricsSink


def test_metrics_sink_records_llm_latency_and_tokens():
    collector = MetricsCollector()
    sink = ObsMetricsSink(collector)

    sink.emit(ObsEvent("llm.latency", "planner", {"model": "gpt-4", "latency_ms": 12.5}))
    sink.emit(ObsEvent("llm.usage", "planner", {
        "model": "gpt-4",
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
    }))

    latency_metric = collector.get_metric("llm_latency_ms")
    total_tokens_metric = collector.get_metric("llm_total_tokens")
    assert latency_metric is not None
    assert total_tokens_metric is not None
    assert latency_metric.get_count() == 1
    assert total_tokens_metric.get_latest_value() == 30


def test_metrics_sink_records_tool_latency_and_errors():
    collector = MetricsCollector()
    sink = ObsMetricsSink(collector)

    sink.emit(ObsEvent("tool.latency", "executor", {"tool": "calc", "latency_ms": 5.0, "success": True}))
    sink.emit(ObsEvent("tool.latency", "executor", {"tool": "calc", "latency_ms": 2.0, "success": False}))

    tool_latency = collector.get_metric("tool_latency_ms")
    tool_errors = collector.get_metric("tool_error")
    assert tool_latency is not None
    assert tool_errors is not None
    assert tool_latency.get_count() == 2
    assert tool_errors.get_sum() == 1.0
