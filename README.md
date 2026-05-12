# Agent SDK

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Agent SDK is a reusable agent runtime for building and embedding AI agents. It ships the planner/executor core, tool/runtime contracts, observability hooks, and local developer surfaces needed to compose agent systems.

Hosted control-plane and SaaS product surfaces now belong to `agent-platform`. A small number of legacy SDK modules remain as deprecated compatibility shims during the migration window.

## Highlights
- Planner + executor runtime with streaming
- Tool registry + packs + schema generation
- Public runtime contracts + integration ports
- Safety and policy hooks for embedded runtimes
- Audit and observability helpers
- Health checks, OpenTelemetry, Prometheus
- Durable queue + scheduler + replay
- CLI utilities for local/dev and compatibility workflows

## Boundary Note

- Canonical hosted API, tenant store, control plane backends, admin UI, dashboard, billing, privacy exports, and webhook delivery now live in `agent-platform`.
- Deprecated SDK shim mappings are documented in `docs/DEPRECATION_POLICY.md`.

## Production-Grade Features

**Runtime Security**
- API keys, JWT auth, RBAC scopes
- Project-scoped API keys
- IP allowlists and rate limits
- Tool allowlists (filesystem + HTTP)
- Identity providers (OIDC/SAML) and SCIM

**Governance & Compliance**
- Policy bundles + approvals + assignments
- Safety policy presets + validation
- Audit logs with hash chaining + export
- Webhooks for run/session/audit events
- Compliance report CLI
- GDPR/CCPA privacy export bundles

**Reliability & Ops**
- Retries, circuit breakers, replay mode
- Durable queues and scheduler
- Provider health checks + failover hooks
- Retention policies and data deletion APIs
- Backup/restore (SQLite/Postgres)

**Observability**
- Structured logs and metrics
- OpenTelemetry export (OTLP/stdout)
- Prometheus metrics endpoint
- Event streaming (SSE)

## Quick Start

### Install
```bash
pip install -e .
```

### Run Tests
```bash
pytest
```

### Run Server (Local)
```bash
export API_KEY="your-key"
python -m agent_sdk.server.app
```

### Execute a Task
```bash
curl -X POST http://localhost:8000/run \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"task": "Summarize this text"}'
```

## CLI
```bash
# Diagnostics
agent-sdk doctor

# Compatibility check
agent-sdk compat upgrade-check 0.2.0

# Backups
agent-sdk backup list

# Compliance report
agent-sdk compliance-report report --output compliance_report.zip
```

## Documentation

Core docs live in `docs/` and delivery plans in `documents/`.

Key references:
- `docs/PRODUCTION_HARDENING.md`
- `docs/BACKUP_RECOVERY.md`
- `docs/OBSERVABILITY.md`
- `docs/RELEASE_HARDENING.md`
- `docs/COMPATIBILITY.md`
- `docs/DEPRECATION_POLICY.md`

## Project Structure (High-Level)
```
agent_sdk/
  core/              # runtime, tools, streaming
  server/            # FastAPI server + admin endpoints
  storage/           # SQLite/Postgres adapters
  observability/     # metrics, tracing, audit logs
  policy/            # governance policy engine
  testing/           # mocks + fixtures
  cli/               # agent-sdk CLI

docs/                # production and ops docs
 documents/          # platform plan and tracking
 deploy/             # helm/k8s/terraform, env examples
 tests/              # test suite
```

## Hosted Surface Note

- If you need the hosted multi-tenant API or control-plane product surface, use `agent-platform`.
- Legacy SDK hosted endpoints are compatibility shims and should not be used as the long-term integration target.

## Deployment
- Docker: `Dockerfile`, `docker-compose.yml`
- K8s/Helm: `deploy/k8s`, `deploy/helm`
- Terraform reference: `deploy/terraform`
- Environment examples: `deploy/env/*.env.example`

## Support Matrix
- Python: 3.9+\n- Storage: SQLite, Postgres\n- OS: macOS, Linux\n\n## Security & Compliance Notes\n- Secrets never need to be committed; use `AGENT_SDK_JWT_SECRET`, secrets managers, or file providers.\n- Audit logs can be exported for compliance and are tamper-evident with hash chaining.\n- Privacy exports available for GDPR/CCPA workflows.\n\n## Status
Phase 1–10 are complete. See `documents/BATTERY_INCLUDED_PLATFORM_PLAN.md` for the full roadmap and status.
