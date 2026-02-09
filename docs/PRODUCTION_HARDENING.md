# Production Hardening Guide

This guide documents the production-grade features added in Phase 4 and how to enable them.

## Security and Access Control
- Org scoping enforced via `X-Org-Id`.
- RBAC and scopes via API keys (`API_KEY_ROLE`, `API_KEY_SCOPES`).
- JWT auth (HS256): `AGENT_SDK_JWT_ENABLED=true`, `AGENT_SDK_JWT_SECRET=...`.
- API key rotation via `/admin/api-keys/{key_id}/rotate`.
- Per-key rate limit and IP allowlist via admin API key creation.
- Tool allowlists: `AGENT_SDK_FS_ALLOWLIST`, `AGENT_SDK_HTTP_ALLOWLIST`.

## Durability and Replay
- Postgres storage for runs/sessions/events (`AGENT_SDK_STORAGE_BACKEND=postgres`).
- Event replay via `/run/{id}/events/replay`.
- Retention via `AGENT_SDK_EVENT_RETENTION_MAX_EVENTS`.
- Run recovery on restart via `AGENT_SDK_RUN_RECOVERY_ENABLED=true`.

## Governance and Compliance
- Audit logging: `AGENT_SDK_AUDIT_LOG_PATH`, `AGENT_SDK_AUDIT_LOG_STDOUT`.
- Data deletion endpoints: `/admin/runs/{id}`, `/admin/sessions/{id}`.
- PII redaction: `AGENT_SDK_PII_REDACTION_ENABLED=true`.

## Model Management and Quotas
- Per-tenant model policies via `/admin/model-policies`.
- Quotas via `/admin/quotas` (runs/sessions/tokens).

## Reliability
- Queue-based execution: `AGENT_SDK_EXECUTION_MODE=queue`, `AGENT_SDK_WORKER_COUNT=4`.
- Durable queue backend: `AGENT_SDK_QUEUE_BACKEND=sqlite`, `AGENT_SDK_QUEUE_DB_PATH=queue.db`.
- Retry policy: `AGENT_SDK_RETRY_MAX`, `AGENT_SDK_RETRY_BASE_DELAY`, `AGENT_SDK_RETRY_MAX_DELAY`.
- Backpressure: `AGENT_SDK_STREAM_QUEUE_SIZE`, `AGENT_SDK_STREAM_MAX_EVENTS`.
- Idempotency for run creation: `Idempotency-Key` header.

## Tool Packs
- Signed manifests: `AGENT_SDK_TOOL_MANIFEST_SECRET`.

## Operations Checklist
1. Configure storage and backups.
2. Set audit logs and redaction policies.
3. Define quotas and model policies per org.
4. Run migrations before deploying new versions.
