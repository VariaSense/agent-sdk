"""Prometheus metrics exporter for Agent SDK observability."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

from prometheus_client.core import GaugeMetricFamily

from agent_sdk import __version__
from agent_sdk.observability.otel import ObservabilityManager


def _attributes_label(attributes: Optional[Dict[str, Any]]) -> str:
    if not attributes:
        return ""
    return json.dumps(attributes, sort_keys=True, separators=(",", ":"))


def _percentile(values: List[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    sorted_values = sorted(values)
    index = int(round((percentile / 100.0) * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(index, len(sorted_values) - 1))]


class ObservabilityPrometheusCollector:
    """Expose ObservabilityManager metrics as Prometheus gauge families."""

    def __init__(self, observability: Optional[ObservabilityManager]) -> None:
        self._observability = observability

    def collect(self) -> Iterable[GaugeMetricFamily]:
        up = GaugeMetricFamily("agent_sdk_up", "Agent SDK process up status")
        up.add_metric([], 1.0)
        yield up

        build = GaugeMetricFamily(
            "agent_sdk_build_info",
            "Agent SDK build information",
            labels=["version"],
        )
        build.add_metric([__version__], 1.0)
        yield build

        if not self._observability:
            return

        metrics = self._observability.metrics.metrics
        grouped: Dict[Tuple[str, str, str], Dict[str, float]] = {}
        for metric in metrics:
            key = (metric.name, metric.unit, _attributes_label(metric.attributes))
            entry = grouped.setdefault(key, {"sum": 0.0, "count": 0.0, "last": 0.0})
            entry["sum"] += metric.value
            entry["count"] += 1.0
            entry["last"] = metric.value

        last_family = GaugeMetricFamily(
            "agent_sdk_metric_last",
            "Latest metric value by name",
            labels=["metric", "unit", "attributes"],
        )
        sum_family = GaugeMetricFamily(
            "agent_sdk_metric_sum",
            "Sum of metric values by name",
            labels=["metric", "unit", "attributes"],
        )
        count_family = GaugeMetricFamily(
            "agent_sdk_metric_count",
            "Count of metric samples by name",
            labels=["metric", "unit", "attributes"],
        )
        for (name, unit, attributes), agg in grouped.items():
            labels = [name, unit, attributes]
            last_family.add_metric(labels, agg["last"])
            sum_family.add_metric(labels, agg["sum"])
            count_family.add_metric(labels, agg["count"])

        yield last_family
        yield sum_family
        yield count_family

        cost_totals: Dict[Tuple[str, str], Dict[str, float]] = {}
        for cost_metric in self._observability.metrics.cost_metrics:
            key = (cost_metric.model, cost_metric.provider)
            entry = cost_totals.setdefault(
                key, {"cost_usd": 0.0, "input_tokens": 0.0, "output_tokens": 0.0, "count": 0.0}
            )
            entry["cost_usd"] += cost_metric.cost_usd
            entry["input_tokens"] += float(cost_metric.input_tokens)
            entry["output_tokens"] += float(cost_metric.output_tokens)
            entry["count"] += 1.0

        cost_family = GaugeMetricFamily(
            "agent_sdk_cost_usd_total",
            "Total cost in USD per model/provider",
            labels=["model", "provider"],
        )
        input_family = GaugeMetricFamily(
            "agent_sdk_input_tokens_total",
            "Total input tokens per model/provider",
            labels=["model", "provider"],
        )
        output_family = GaugeMetricFamily(
            "agent_sdk_output_tokens_total",
            "Total output tokens per model/provider",
            labels=["model", "provider"],
        )
        cost_count_family = GaugeMetricFamily(
            "agent_sdk_cost_sample_count",
            "Cost metric samples per model/provider",
            labels=["model", "provider"],
        )
        for (model, provider), totals in cost_totals.items():
            labels = [model, provider]
            cost_family.add_metric(labels, totals["cost_usd"])
            input_family.add_metric(labels, totals["input_tokens"])
            output_family.add_metric(labels, totals["output_tokens"])
            cost_count_family.add_metric(labels, totals["count"])

        yield cost_family
        yield input_family
        yield output_family
        yield cost_count_family

        latency_family = GaugeMetricFamily(
            "agent_sdk_latency_avg_ms",
            "Average latency per operation",
            labels=["operation"],
        )
        latency_p95_family = GaugeMetricFamily(
            "agent_sdk_latency_p95_ms",
            "P95 latency per operation",
            labels=["operation"],
        )
        latency_count_family = GaugeMetricFamily(
            "agent_sdk_latency_count",
            "Latency samples per operation",
            labels=["operation"],
        )
        for operation, samples in self._observability.metrics.latency_samples.items():
            avg = sum(samples) / len(samples)
            p95 = _percentile(samples, 95)
            latency_family.add_metric([operation], avg)
            if p95 is not None:
                latency_p95_family.add_metric([operation], p95)
            latency_count_family.add_metric([operation], float(len(samples)))

        yield latency_family
        yield latency_p95_family
        yield latency_count_family
