# Observability Guide

This guide describes tracing and metrics integrations for production deployments.

## Prometheus Metrics

Enable the metrics endpoint by setting:
- `AGENT_SDK_PROMETHEUS_ENABLED=true`

Then scrape `http://<host>:<port>/metrics`.

## OpenTelemetry Tracing

Agent SDK can mirror spans to OpenTelemetry exporters.

### Exporter Presets
- `AGENT_SDK_OTEL_EXPORTER=otlp` (OTLP HTTP exporter)
- `AGENT_SDK_OTEL_EXPORTER=stdout` (console exporter)
- `AGENT_SDK_OTEL_EXPORTER=none` (default)

### OTLP Endpoint
Set the collector endpoint:
- `AGENT_SDK_OTEL_OTLP_ENDPOINT=http://collector:4318/v1/traces`

### Example
```
AGENT_SDK_TRACING_ENABLED=true
AGENT_SDK_OTEL_EXPORTER=otlp
AGENT_SDK_OTEL_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```
