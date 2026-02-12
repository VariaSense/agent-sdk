# Agent SDK

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Agent SDK is a battery-included platform for building and operating AI agents. It ships a planner/executor runtime, multi-tenant control plane, observability, governance, and deployment scaffolding so teams can ship production platforms without custom glue.

## Highlights
- Planner + executor runtime with streaming
- Tool registry + packs + schema generation
- Multi-tenant org/project model and API keys
- Policy bundles, approvals, and safety guardrails
- Audit logs with hash chaining and export
- Webhooks with retries/DLQ and signatures
- Usage, quotas, retention, and privacy exports
- Health checks, OpenTelemetry, Prometheus
- Durable queue + scheduler + replay
- CLI utilities for ops, backup, compliance
- Docker/K8s/Helm + Terraform references

## Production-Grade Features

**Security & Access**
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

## Admin API Surface (Selected)
- `POST /admin/projects`, `GET /admin/projects`, `DELETE /admin/projects/{id}`
- `POST /admin/api-keys`, `GET /admin/api-keys`, `DELETE /admin/api-keys/{id}`
- `POST /admin/policy-bundles`, `POST /admin/policy-approvals`, `POST /admin/policy-assignments`
- `POST /admin/quotas`, `POST /admin/quotas/projects`, `POST /admin/quotas/api-keys`
- `GET /admin/usage`, `GET /admin/usage/export`, `GET /admin/usage/projects`, `GET /admin/usage/api-keys`
- `POST /admin/archives/export`, `POST /admin/archives/restore`
- `POST /admin/privacy/export`
- `GET /admin/providers/health`

## Deployment
- Docker: `Dockerfile`, `docker-compose.yml`
- K8s/Helm: `deploy/k8s`, `deploy/helm`
- Terraform reference: `deploy/terraform`
- Environment examples: `deploy/env/*.env.example`

## Support Matrix
- Python: 3.9+\n- Storage: SQLite, Postgres\n- OS: macOS, Linux\n\n## Security & Compliance Notes\n- Secrets never need to be committed; use `AGENT_SDK_JWT_SECRET`, secrets managers, or file providers.\n- Audit logs can be exported for compliance and are tamper-evident with hash chaining.\n- Privacy exports available for GDPR/CCPA workflows.\n\n## Status
Phase 1–10 are complete. See `documents/BATTERY_INCLUDED_PLATFORM_PLAN.md` for the full roadmap and status.
