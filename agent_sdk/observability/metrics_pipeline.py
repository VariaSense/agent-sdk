"""Metrics pipeline that converts ObsEvent events into structured metrics."""

from __future__ import annotations

from typing import Optional, Dict

from agent_sdk.observability.sinks import EventSink
from agent_sdk.observability.events import ObsEvent
from agent_sdk.observability.metrics import MetricsCollector, MetricType


class ObsMetricsSink(EventSink):
    """Translate observability events into metrics."""

    def __init__(self, collector: Optional[MetricsCollector] = None):
        self.collector = collector or MetricsCollector()
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.collector.register_metric(
            "llm_latency_ms",
            MetricType.HISTOGRAM,
            unit="ms",
            description="LLM request latency in milliseconds",
        )
        self.collector.register_metric(
            "llm_prompt_tokens",
            MetricType.HISTOGRAM,
            unit="tokens",
            description="Prompt token usage per LLM request",
        )
        self.collector.register_metric(
            "llm_completion_tokens",
            MetricType.HISTOGRAM,
            unit="tokens",
            description="Completion token usage per LLM request",
        )
        self.collector.register_metric(
            "llm_total_tokens",
            MetricType.HISTOGRAM,
            unit="tokens",
            description="Total token usage per LLM request",
        )
        self.collector.register_metric(
            "tool_latency_ms",
            MetricType.HISTOGRAM,
            unit="ms",
            description="Tool execution latency in milliseconds",
        )
        self.collector.register_metric(
            "tool_error",
            MetricType.COUNTER,
            unit="count",
            description="Tool execution errors",
        )

    def emit(self, event: ObsEvent):
        event_type = event.event_type
        data = event.data or {}

        if event_type == "llm.latency":
            model = data.get("model", "unknown")
            self.collector.record_metric(
                "llm_latency_ms",
                float(data.get("latency_ms", 0)),
                labels={"model": model},
            )
            return

        if event_type == "llm.usage":
            model = data.get("model", "unknown")
            labels = {"model": model}
            self.collector.record_metric(
                "llm_prompt_tokens",
                float(data.get("prompt_tokens", 0)),
                labels=labels,
            )
            self.collector.record_metric(
                "llm_completion_tokens",
                float(data.get("completion_tokens", 0)),
                labels=labels,
            )
            self.collector.record_metric(
                "llm_total_tokens",
                float(data.get("total_tokens", 0)),
                labels=labels,
            )
            return

        if event_type == "tool.latency":
            tool = data.get("tool", "unknown")
            success = bool(data.get("success", True))
            self.collector.record_metric(
                "tool_latency_ms",
                float(data.get("latency_ms", 0)),
                labels={"tool": tool, "success": str(success).lower()},
            )
            if not success:
                self.collector.record_metric(
                    "tool_error",
                    1.0,
                    labels={"tool": tool},
                )
