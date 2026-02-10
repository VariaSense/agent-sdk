# Production Hardening Guide

This guide documents the production-grade features added in Phase 4 and how to enable them.

## Security and Access Control
- Org scoping enforced via `X-Org-Id`.
- RBAC and scopes via API keys (`API_KEY_ROLE`, `API_KEY_SCOPES`).
- JWT auth (HS256): `AGENT_SDK_JWT_ENABLED=true`, `AGENT_SDK_JWT_SECRET=...`.
- API key rotation via `/admin/api-keys/{key_id}/rotate`.
- Per-key rate limit and IP allowlist via admin API key creation.
- Tool allowlists: `AGENT_SDK_FS_ALLOWLIST`, `AGENT_SDK_HTTP_ALLOWLIST`.
- Secrets providers: env/file + Vault + AWS/GCP/Azure secret managers (see `agent_sdk/secrets.py`).
- Identity providers: `AGENT_SDK_IDP_PROVIDER=mock|oidc|saml` with `/auth/validate`.
- SCIM provisioning: set `AGENT_SDK_SCIM_TOKEN` and use `/scim/v2/Users`.

## Durability and Replay
- Postgres storage for runs/sessions/events (`AGENT_SDK_STORAGE_BACKEND=postgres`).
- Event replay via `/run/{id}/events/replay`.
- Retention via `AGENT_SDK_EVENT_RETENTION_MAX_EVENTS`.
- Run recovery on restart via `AGENT_SDK_RUN_RECOVERY_ENABLED=true`.
- Per-tenant retention via `/admin/retention`.

## Governance and Compliance
- Audit logging: `AGENT_SDK_AUDIT_LOG_PATH`, `AGENT_SDK_AUDIT_LOG_STDOUT`.
- Audit hash chaining: `AGENT_SDK_AUDIT_HASH_CHAIN=true` (tamper-evident logs).
- Audit export: `/admin/audit-logs/export?format=jsonl|csv`.
- Data deletion endpoints: `/admin/runs/{id}`, `/admin/sessions/{id}`.
- PII redaction: `AGENT_SDK_PII_REDACTION_ENABLED=true`.
- Data residency: set org residency via `/admin/residency` and enforce with `AGENT_SDK_DATA_REGION`.
- Encryption at rest: enable with `AGENT_SDK_ENCRYPTION_ENABLED=true` and set per-tenant keys via `/admin/encryption-keys`.

## Model Management and Quotas
- Per-tenant model policies via `/admin/model-policies`.
- Quotas via `/admin/quotas` (runs/sessions/tokens).
- Usage export: `/admin/usage/export?group_by=org_id,project` (CSV/JSON).

## Reliability
- Queue-based execution: `AGENT_SDK_EXECUTION_MODE=queue`, `AGENT_SDK_WORKER_COUNT=4`.
- Durable queue backend: `AGENT_SDK_QUEUE_BACKEND=sqlite`, `AGENT_SDK_QUEUE_DB_PATH=queue.db`.
- Redis queue backend: `AGENT_SDK_QUEUE_BACKEND=redis`, `AGENT_SDK_REDIS_URL=redis://host:6379/0`.
- SQS queue backend: `AGENT_SDK_QUEUE_BACKEND=sqs`, `AGENT_SDK_SQS_QUEUE_URL=...`.
- Kafka queue backend: `AGENT_SDK_QUEUE_BACKEND=kafka`, `AGENT_SDK_KAFKA_TOPIC=agent-sdk-jobs`.
- Retry policy: `AGENT_SDK_RETRY_MAX`, `AGENT_SDK_RETRY_BASE_DELAY`, `AGENT_SDK_RETRY_MAX_DELAY`.
- Tool reliability policies: `AGENT_SDK_RELIABILITY_ENABLED=true`, `AGENT_SDK_TOOL_RETRY_MAX`, `AGENT_SDK_TOOL_CIRCUIT_FAILURE_THRESHOLD`.
- Replay mode: `AGENT_SDK_REPLAY_MODE=true`, optional `AGENT_SDK_REPLAY_PATH` for cached tool outputs.
- Backpressure: `AGENT_SDK_STREAM_QUEUE_SIZE`, `AGENT_SDK_STREAM_MAX_EVENTS`.
- Idempotency for run creation: `Idempotency-Key` header.
- Scheduled runs via `/admin/schedules` with cron expressions.
- Durable scheduler: set `AGENT_SDK_SCHEDULER_DB_PATH` to persist schedules.

## Tool Sandboxing
- Enable local sandbox: `AGENT_SDK_TOOL_SANDBOX=local`, `AGENT_SDK_TOOL_SANDBOX_TIMEOUT=10`.
- Docker sandbox is a stub (`AGENT_SDK_TOOL_SANDBOX=docker` requires external integration).

## Metrics and Monitoring
- Prometheus endpoint: set `AGENT_SDK_PROMETHEUS_ENABLED=true`, scrape `/metrics`.

## Tracing Export (OpenTelemetry)
- Enable exporter preset: `AGENT_SDK_OTEL_EXPORTER=otlp` or `AGENT_SDK_OTEL_EXPORTER=stdout`.
- OTLP endpoint (HTTP): `AGENT_SDK_OTEL_OTLP_ENDPOINT=http://collector:4318/v1/traces`.

## Tool Packs
- Signed manifests: `AGENT_SDK_TOOL_MANIFEST_SECRET`.
- Local registry CLI: `agent-sdk registry publish|list|pull`.

## Operations Checklist
1. Configure storage and backups (see `docs/BACKUP_RECOVERY.md`).
2. Set audit logs and redaction policies.
3. Define quotas and model policies per org.
4. Run migrations before deploying new versions.

## Kubernetes Deployment
- Manifests live in `deploy/k8s/` (Deployment, Service, HPA).
- Probes: `/health` for liveness and `/ready` for readiness.
- HPA uses CPU utilization (requires metrics-server).
- Helm chart: `deploy/helm/agent-sdk`.

## Release Hardening
- SBOM + vulnerability scanning guidance in `docs/RELEASE_HARDENING.md`.

## API Versioning
- Prefer versioned paths: `/v1/...`.
- Unversioned API requests include `X-API-Deprecated` warning header.
