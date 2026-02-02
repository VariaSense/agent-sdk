"""
OpenTelemetry Integration for Distributed Tracing and Metrics

Implements comprehensive observability with:
- Distributed tracing for multi-agent systems
- Metrics collection (latency, tokens, costs)
- Span context propagation
- Cost tracking integration
- Performance monitoring
- Error tracking

Reference: https://opentelemetry.io/
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import time
import json
import logging
from contextlib import contextmanager


logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    """OpenTelemetry span kinds."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(str, Enum):
    """Span completion status."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanAttribute:
    """A span attribute (key-value pair)."""

    key: str
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {"key": self.key, "value": str(value)}


@dataclass
class SpanEvent:
    """An event that occurred during a span."""

    name: str
    timestamp: datetime = field(default_factory=datetime.now)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "attributes": self.attributes,
        }


@dataclass
class Span:
    """
    OpenTelemetry Span for tracing.

    Represents a unit of work within a trace.
    """

    name: str
    span_id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    kind: SpanKind = SpanKind.INTERNAL
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    error_message: Optional[str] = None

    def add_attribute(self, key: str, value: Any) -> None:
        """Add an attribute to the span."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        event = SpanEvent(name=name, attributes=attributes or {})
        self.events.append(event)

    def set_error(self, error_message: str) -> None:
        """Mark span as error and record message."""
        self.status = SpanStatus.ERROR
        self.error_message = error_message

    def end(self) -> None:
        """End the span."""
        self.end_time = datetime.now()
        if self.status == SpanStatus.UNSET:
            self.status = SpanStatus.OK

    def duration_ms(self) -> float:
        """Get span duration in milliseconds."""
        end = self.end_time or datetime.now()
        delta = end - self.start_time
        return delta.total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary."""
        return {
            "name": self.name,
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms(),
            "status": self.status.value,
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
            "error_message": self.error_message,
        }


@dataclass
class Metric:
    """
    OpenTelemetry Metric for measurements.

    Records numerical measurements over time.
    """

    name: str
    unit: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "unit": self.unit,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "attributes": self.attributes,
        }


@dataclass
class CostMetric:
    """Track API costs and token usage."""

    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "timestamp": self.timestamp.isoformat(),
        }


class TracingProvider:
    """
    OpenTelemetry tracing provider.

    Manages spans, traces, and distributed tracing context.
    """

    def __init__(self, service_name: str = "agent-sdk"):
        """
        Initialize tracing provider.

        Args:
            service_name: Name of the service for tracing
        """
        self.service_name = service_name
        self.spans: Dict[str, Span] = {}
        self.current_trace_id: Optional[str] = None
        self.current_span_id: Optional[str] = None

    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """
        Start a new span.

        Args:
            name: Name of the span
            kind: Type of span
            attributes: Initial attributes

        Returns:
            New Span object
        """
        import uuid

        trace_id = self.current_trace_id or str(uuid.uuid4())[:8]
        span_id = str(uuid.uuid4())[:8]
        parent_span_id = self.current_span_id

        span = Span(
            name=name,
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            kind=kind,
            attributes=attributes or {},
        )

        self.spans[span_id] = span
        self.current_span_id = span_id
        self.current_trace_id = trace_id

        logger.debug(f"Started span: {name} ({span_id})")
        return span

    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK) -> None:
        """
        End a span.

        Args:
            span: Span to end
            status: Final status
        """
        span.status = status
        span.end()
        logger.debug(f"Ended span: {span.name} ({span.span_id})")

    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace."""
        return [s for s in self.spans.values() if s.trace_id == trace_id]

    @contextmanager
    def trace(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Context manager for spans."""
        span = self.start_span(name, kind, attributes)
        try:
            yield span
            self.end_span(span, SpanStatus.OK)
        except Exception as e:
            self.end_span(span, SpanStatus.ERROR)
            span.set_error(str(e))
            raise

    def to_dict(self) -> Dict[str, Any]:
        """Convert all spans to dictionary."""
        return {
            "service_name": self.service_name,
            "spans": [s.to_dict() for s in self.spans.values()],
            "trace_count": len(set(s.trace_id for s in self.spans.values())),
        }


class MetricsCollector:
    """
    Collects and aggregates metrics.

    Tracks latency, tokens, costs, and other performance metrics.
    """

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: List[Metric] = []
        self.cost_metrics: List[CostMetric] = []
        self.latency_samples: Dict[str, List[float]] = {}

    def record_metric(
        self, name: str, value: float, unit: str = "", attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a metric.

        Args:
            name: Metric name
            value: Metric value
            unit: Unit of measurement
            attributes: Optional attributes
        """
        metric = Metric(name=name, unit=unit, value=value, attributes=attributes or {})
        self.metrics.append(metric)
        logger.debug(f"Recorded metric: {name}={value}{unit}")

    def record_latency(self, operation: str, latency_ms: float) -> None:
        """
        Record operation latency.

        Args:
            operation: Operation name
            latency_ms: Latency in milliseconds
        """
        if operation not in self.latency_samples:
            self.latency_samples[operation] = []
        self.latency_samples[operation].append(latency_ms)
        self.record_metric(f"{operation}_latency", latency_ms, unit="ms")

    def record_cost(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """
        Record API cost.

        Args:
            model: Model name
            provider: Provider name
            input_tokens: Input tokens
            output_tokens: Output tokens
            cost_usd: Cost in USD
        """
        cost_metric = CostMetric(
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
        self.cost_metrics.append(cost_metric)
        logger.debug(f"Recorded cost: {model} ${cost_usd:.4f}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregated statistics."""
        latency_stats = {}
        for op, samples in self.latency_samples.items():
            if samples:
                latency_stats[op] = {
                    "count": len(samples),
                    "min_ms": min(samples),
                    "max_ms": max(samples),
                    "avg_ms": sum(samples) / len(samples),
                }

        total_cost = sum(m.cost_usd for m in self.cost_metrics)
        total_input_tokens = sum(m.input_tokens for m in self.cost_metrics)
        total_output_tokens = sum(m.output_tokens for m in self.cost_metrics)

        return {
            "metric_count": len(self.metrics),
            "cost_count": len(self.cost_metrics),
            "total_cost_usd": total_cost,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "latency_statistics": latency_stats,
            "cost_by_model": self._group_costs_by_model(),
        }

    def _group_costs_by_model(self) -> Dict[str, float]:
        """Group costs by model."""
        costs = {}
        for metric in self.cost_metrics:
            key = f"{metric.provider}/{metric.model}"
            costs[key] = costs.get(key, 0) + metric.cost_usd
        return costs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metrics": [m.to_dict() for m in self.metrics],
            "cost_metrics": [c.to_dict() for c in self.cost_metrics],
            "statistics": self.get_statistics(),
        }


class ObservabilityManager:
    """
    Unified observability management.

    Combines tracing, metrics, and cost tracking.
    """

    def __init__(self, service_name: str = "agent-sdk"):
        """Initialize observability manager."""
        self.tracer = TracingProvider(service_name)
        self.metrics = MetricsCollector()
        self.service_name = service_name

    def trace_agent_execution(self, agent_name: str, goal: str):
        """
        Context manager for agent execution tracing.

        Args:
            agent_name: Name of the agent
            goal: Goal/task description

        Yields:
            Span object
        """
        return self.tracer.trace(
            f"agent_execute:{agent_name}",
            kind=SpanKind.INTERNAL,
            attributes={"agent": agent_name, "goal": goal},
        )

    def trace_tool_call(self, tool_name: str, input_params: Dict[str, Any]):
        """
        Context manager for tool invocation tracing.

        Args:
            tool_name: Name of the tool
            input_params: Input parameters

        Yields:
            Span object
        """
        return self.tracer.trace(
            f"tool_call:{tool_name}",
            kind=SpanKind.CLIENT,
            attributes={"tool": tool_name, "params": str(input_params)},
        )

    def trace_model_call(self, model_name: str, provider: str):
        """
        Context manager for model API call tracing.

        Args:
            model_name: Name of the model
            provider: Provider name (openai, anthropic, etc.)

        Yields:
            Span object
        """
        return self.tracer.trace(
            f"model_call:{provider}",
            kind=SpanKind.CLIENT,
            attributes={"model": model_name, "provider": provider},
        )

    def record_tool_execution(
        self, tool_name: str, latency_ms: float, success: bool, error: Optional[str] = None
    ) -> None:
        """
        Record tool execution metrics.

        Args:
            tool_name: Tool name
            latency_ms: Execution time in milliseconds
            success: Whether execution succeeded
            error: Error message if failed
        """
        self.metrics.record_latency(f"tool_{tool_name}", latency_ms)
        self.metrics.record_metric(f"tool_{tool_name}_success", float(success))
        if error:
            self.metrics.record_metric(f"tool_{tool_name}_error", 1.0)

    def record_model_execution(
        self,
        model_name: str,
        provider: str,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
    ) -> None:
        """
        Record model execution metrics.

        Args:
            model_name: Model name
            provider: Provider name
            latency_ms: Execution time in milliseconds
            input_tokens: Input tokens used
            output_tokens: Output tokens generated
            cost_usd: Cost in USD
        """
        self.metrics.record_latency(f"model_{provider}", latency_ms)
        self.metrics.record_cost(model_name, provider, input_tokens, output_tokens, cost_usd)

    def get_summary(self) -> Dict[str, Any]:
        """Get complete observability summary."""
        return {
            "service": self.service_name,
            "tracing": self.tracer.to_dict(),
            "metrics": self.metrics.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }

    def export_json(self) -> str:
        """Export all observability data as JSON."""
        return json.dumps(self.get_summary(), indent=2)


def create_observability_manager(service_name: str = "agent-sdk") -> ObservabilityManager:
    """
    Factory function to create observability manager.

    Args:
        service_name: Name of the service

    Returns:
        Configured ObservabilityManager
    """
    return ObservabilityManager(service_name)


__all__ = [
    "SpanKind",
    "SpanStatus",
    "Span",
    "SpanEvent",
    "Metric",
    "CostMetric",
    "TracingProvider",
    "MetricsCollector",
    "ObservabilityManager",
    "create_observability_manager",
]
