"""
Metrics collection and reporting for Agent SDK.

Provides performance metrics, operation metrics, and custom metric tracking.

Features:
- Operation-level metrics (latency, throughput)
- Agent-level metrics (success rate, avg tokens)
- Tool-level metrics (execution time per tool)
- Custom metrics and aggregation
- Metrics export and reporting
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import json


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"  # Cumulative count
    GAUGE = "gauge"      # Point-in-time value
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"  # Aggregated statistics


@dataclass
class Measurement:
    """A single metric measurement."""
    timestamp: datetime
    value: float
    unit: str = ""
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "unit": self.unit,
            "labels": self.labels
        }


@dataclass
class MetricData:
    """Data for a single metric."""
    name: str
    metric_type: MetricType
    unit: str = ""
    description: str = ""
    measurements: List[Measurement] = field(default_factory=list)
    
    def add_measurement(self, value: float, timestamp: Optional[datetime] = None, labels: Optional[Dict] = None) -> None:
        """Add a measurement."""
        measurement = Measurement(
            timestamp=timestamp or datetime.now(),
            value=value,
            unit=self.unit,
            labels=labels or {}
        )
        self.measurements.append(measurement)
    
    def get_latest_value(self) -> Optional[float]:
        """Get the latest measurement value."""
        if not self.measurements:
            return None
        return self.measurements[-1].value
    
    def get_count(self) -> int:
        """Get count of measurements."""
        return len(self.measurements)
    
    def get_sum(self) -> float:
        """Get sum of all measurements."""
        return sum(m.value for m in self.measurements)
    
    def get_average(self) -> Optional[float]:
        """Get average of measurements."""
        if not self.measurements:
            return None
        return self.get_sum() / len(self.measurements)
    
    def get_min(self) -> Optional[float]:
        """Get minimum value."""
        if not self.measurements:
            return None
        return min(m.value for m in self.measurements)
    
    def get_max(self) -> Optional[float]:
        """Get maximum value."""
        if not self.measurements:
            return None
        return max(m.value for m in self.measurements)
    
    def get_percentile(self, percentile: float) -> Optional[float]:
        """Get percentile value (0-100)."""
        if not self.measurements:
            return None
        sorted_values = sorted([m.value for m in self.measurements])
        index = int((percentile / 100) * len(sorted_values)) - 1
        return sorted_values[max(0, index)]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "unit": self.unit,
            "description": self.description,
            "count": self.get_count(),
            "latest_value": self.get_latest_value(),
            "sum": self.get_sum(),
            "average": self.get_average(),
            "min": self.get_min(),
            "max": self.get_max(),
            "p50": self.get_percentile(50),
            "p99": self.get_percentile(99),
            "measurements": [m.to_dict() for m in self.measurements[-100:]]  # Last 100
        }


class MetricsCollector:
    """Collects and manages metrics."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, MetricData] = {}
    
    def register_metric(
        self,
        name: str,
        metric_type: MetricType,
        unit: str = "",
        description: str = ""
    ) -> MetricData:
        """Register a new metric."""
        metric = MetricData(
            name=name,
            metric_type=metric_type,
            unit=unit,
            description=description
        )
        self.metrics[name] = metric
        return metric
    
    def record_metric(
        self,
        name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a metric measurement."""
        if name not in self.metrics:
            raise ValueError(f"Metric {name} not registered")
        
        self.metrics[name].add_measurement(value, timestamp, labels)
    
    def get_metric(self, name: str) -> Optional[MetricData]:
        """Get metric data."""
        return self.metrics.get(name)
    
    def get_all_metrics(self) -> Dict[str, MetricData]:
        """Get all metrics."""
        return self.metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        return {
            name: metric.to_dict()
            for name, metric in self.metrics.items()
        }
    
    def clear(self) -> None:
        """Clear all metrics."""
        self.metrics.clear()
    
    def export_to_json(self, filepath: str) -> None:
        """Export metrics to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": self.get_summary()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


@dataclass
class PerformanceMetrics:
    """Performance metrics for an operation."""
    operation_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    token_count: int = 0
    tokens_per_second: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def mark_complete(self, end_time: Optional[datetime] = None) -> None:
        """Mark operation as complete."""
        self.end_time = end_time or datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        
        if self.duration_ms > 0 and self.token_count > 0:
            self.tokens_per_second = (self.token_count / self.duration_ms) * 1000
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "operation_name": self.operation_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "token_count": self.token_count,
            "tokens_per_second": self.tokens_per_second,
            "success": self.success,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


@dataclass
class OperationMetrics:
    """Aggregated metrics for a type of operation."""
    operation_type: str
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    total_duration_ms: float = 0.0
    total_tokens: int = 0
    latencies: List[float] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Get success rate."""
        if self.total_operations == 0:
            return 0.0
        return self.successful_operations / self.total_operations
    
    @property
    def failure_rate(self) -> float:
        """Get failure rate."""
        return 1.0 - self.success_rate
    
    @property
    def average_latency_ms(self) -> float:
        """Get average latency."""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)
    
    @property
    def p99_latency_ms(self) -> Optional[float]:
        """Get 99th percentile latency."""
        if not self.latencies:
            return None
        sorted_latencies = sorted(self.latencies)
        index = int(0.99 * len(sorted_latencies)) - 1
        return sorted_latencies[max(0, index)]
    
    @property
    def average_tokens_per_operation(self) -> float:
        """Get average tokens per operation."""
        if self.total_operations == 0:
            return 0.0
        return self.total_tokens / self.total_operations
    
    @property
    def throughput_ops_per_second(self) -> float:
        """Get throughput in operations per second."""
        if self.total_duration_ms == 0:
            return 0.0
        return (self.total_operations / self.total_duration_ms) * 1000
    
    def add_operation(self, duration_ms: float, token_count: int, success: bool) -> None:
        """Add a single operation metric."""
        self.total_operations += 1
        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1
        
        self.total_duration_ms += duration_ms
        self.total_tokens += token_count
        self.latencies.append(duration_ms)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "operation_type": self.operation_type,
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "success_rate": round(self.success_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
            "total_duration_ms": round(self.total_duration_ms, 2),
            "average_latency_ms": round(self.average_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2) if self.p99_latency_ms else None,
            "total_tokens": self.total_tokens,
            "average_tokens_per_operation": round(self.average_tokens_per_operation, 2),
            "throughput_ops_per_second": round(self.throughput_ops_per_second, 4)
        }


class OperationMetricsTracker:
    """Tracks aggregated metrics for operations."""
    
    def __init__(self):
        """Initialize tracker."""
        self.metrics: Dict[str, OperationMetrics] = {}
    
    def record_operation(
        self,
        operation_type: str,
        duration_ms: float,
        token_count: int = 0,
        success: bool = True
    ) -> None:
        """Record an operation."""
        if operation_type not in self.metrics:
            self.metrics[operation_type] = OperationMetrics(operation_type)
        
        self.metrics[operation_type].add_operation(duration_ms, token_count, success)
    
    def get_operation_metrics(self, operation_type: str) -> Optional[OperationMetrics]:
        """Get metrics for a specific operation type."""
        return self.metrics.get(operation_type)
    
    def get_all_metrics(self) -> Dict[str, OperationMetrics]:
        """Get all operation metrics."""
        return self.metrics
    
    def get_summary(self) -> Dict[str, Dict]:
        """Get summary of all operation metrics."""
        return {
            op_type: metrics.to_dict()
            for op_type, metrics in self.metrics.items()
        }
    
    def clear(self) -> None:
        """Clear all metrics."""
        self.metrics.clear()
    
    def export_to_json(self, filepath: str) -> None:
        """Export metrics to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "operations": self.get_summary()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
