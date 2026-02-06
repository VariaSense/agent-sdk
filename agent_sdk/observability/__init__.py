"""
Observability module for Agent SDK.

Provides tracing, metrics, cost tracking, and performance profiling.

Main Components:
- OpenTelemetry integration (otel.py)
- Cost tracking (cost_tracker.py)
- Metrics collection (metrics.py)
- Performance profiling (profiler.py)
- Event bus (bus.py)
- Event definitions (events.py)
"""

# Cost tracking
from agent_sdk.observability.cost_tracker import (
    CostTracker,
    CostUnit,
    ModelPricing,
    TokenUsage,
    OperationCost,
    CostSummary,
    create_cost_tracker,
    OPENAI_PRICING,
    ANTHROPIC_PRICING
)

# Metrics collection
from agent_sdk.observability.metrics import (
    MetricsCollector,
    MetricType,
    MetricData,
    Measurement,
    PerformanceMetrics,
    OperationMetrics,
    OperationMetricsTracker
)

# Performance profiling
from agent_sdk.observability.profiler import (
    PerformanceProfiler,
    OperationTiming,
    MemorySnapshot,
    CriticalPathAnalysis,
    BottleneckAnalysis,
    create_profiler
)

# Event bus and events
from agent_sdk.observability.bus import EventBus
from agent_sdk.observability.events import ObsEvent
from agent_sdk.observability.stream_envelope import (
    StreamChannel,
    RunStatus,
    RunMetadata,
    SessionMetadata,
    StreamEnvelope,
    new_run_id,
    new_session_id,
)

# OpenTelemetry
from agent_sdk.observability.otel import ObservabilityManager
from agent_sdk.observability.run_logs import (
    RunLogExporter,
    JSONLFileExporter,
    StdoutExporter,
    create_run_log_exporters,
)
from agent_sdk.observability.metrics_pipeline import ObsMetricsSink

__all__ = [
    # Cost tracking
    "CostTracker",
    "CostUnit",
    "ModelPricing",
    "TokenUsage",
    "OperationCost",
    "CostSummary",
    "create_cost_tracker",
    "OPENAI_PRICING",
    "ANTHROPIC_PRICING",
    
    # Metrics
    "MetricsCollector",
    "MetricType",
    "MetricData",
    "Measurement",
    "PerformanceMetrics",
    "OperationMetrics",
    "OperationMetricsTracker",
    
    # Profiling
    "PerformanceProfiler",
    "OperationTiming",
    "MemorySnapshot",
    "CriticalPathAnalysis",
    "BottleneckAnalysis",
    "create_profiler",
    
    # Events
    "EventBus",
    "ObsEvent",
    "StreamChannel",
    "RunStatus",
    "RunMetadata",
    "SessionMetadata",
    "StreamEnvelope",
    "new_run_id",
    "new_session_id",
    "RunLogExporter",
    "JSONLFileExporter",
    "StdoutExporter",
    "create_run_log_exporters",
    "ObsMetricsSink",
    
    # OpenTelemetry
    "ObservabilityManager"
]
