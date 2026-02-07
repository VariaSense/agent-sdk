# Agent SDK Battery-Included Platform Plan

## Purpose
Deliver a "battery-included" experience on top of agent-sdk while keeping the SDK as the stable agent runtime. This plan defines what to build, in what order, and the concrete deliverables to track implementation.

## Current Status (as of 2026-02-07)
- Phase 1: Local-first MVP complete.
- Phase 2: Developer experience + reliability complete.
- Phase 3: Platform extensions complete.
- Phase 4: Production hardening in progress (tasks 1-8 complete).

## Scope and Principles
- Keep agent-sdk as the "agent brain" and developer runtime.
- Build a minimal, local-first platform experience that can later scale to multi-tenant SaaS.
- Favor shipping a working MVP quickly with clean extension points.
- Minimize external infra requirements in Phase 1.

## Target Outcomes
- A local single-node platform that lets developers run and observe agents with streaming.
- A set of opinionated presets and tool packs that reduce time-to-first-result.
- A stable, versioned API surface for tools, events, and memory.

## Definitions
- SDK: agent-sdk library/runtime.
- Platform: local UI + API server + storage + orchestration built on top of SDK.
- Battery-included: presets, built-in tools, and dev UI that work out of the box.

---

## Phase 0: Baseline and Alignment (1 week)

### Goals
- Lock the boundary between SDK and platform.
- Define success criteria and measurable milestones.

### Deliverables
- Architecture boundary doc (SDK vs platform ownership).
- MVP scope checklist.
- Milestone timeline.

### Tasks
- Review current SDK runtime and APIs.
- Document SDK responsibilities:
  - agent loop semantics
  - tool lifecycle
  - model routing
  - memory semantics
  - observability hooks
- Document platform responsibilities:
  - UI/UX
  - API server surface
  - storage
  - scheduling
  - deployment

### Exit Criteria
- Written boundary doc.
- Prioritized backlog with estimates.

---

## Phase 1: Local-First Battery Included MVP (4-6 weeks)

### Objective
Ship a local "mini-platform" that provides streaming runs, UI, and storage using only local dependencies.

### 1.1 SDK Enhancements (minimal additions)
- Add stable event schema for `assistant`, `tool`, `lifecycle` streams.
- Add run/session identifiers and metadata.
- Add a simple pluggable storage interface for sessions and run logs.
- Add tool schema validation (strict) and version metadata.

Deliverables:
- `agent_sdk/observability` streaming event spec.
- `agent_sdk/runtime` run metadata model.
- `agent_sdk/storage` interface (default SQLite adapter optional).

### 1.2 Local API Server
- FastAPI server endpoints:
  - `POST /run` (start run)
  - `GET /run/{id}` (status)
  - `GET /run/{id}/events` (SSE stream)
  - `GET /sessions` and `GET /sessions/{id}`
- Local auth: API key in env.

Deliverables:
- `agent_sdk/server` with SSE streaming and basic auth.
- API docs (OpenAPI auto docs).

### 1.3 Local UI (Dev Console)
- Minimal web UI to:
  - submit prompts
  - stream output
  - inspect tool calls
  - view session history
- Prefer a single-page UI served by the FastAPI server.

Deliverables:
- `agent_sdk/ui` static bundle.
- Integrated UI route `/` on local server.

### 1.4 Battery-Included Presets
- Presets for common workflows:
  - `assistant_basic`
  - `assistant_tools`
  - `assistant_rag`
  - `assistant_multiagent`
- Each preset includes model config, tool pack, memory policy.

Deliverables:
- `agent_sdk/presets` module.
- CLI: `agent-sdk run --preset assistant_basic`.

### 1.5 Tool Packs
- Built-in tools packaged with schema and metadata:
  - `filesystem.read`, `filesystem.write`
  - `http.fetch` (with allowlist)
  - `calculator`
  - `time`
  - `vector.search` (optional local)

Deliverables:
- `agent_sdk/tools/builtin` with schemas.
- Tool registry auto-loads builtin pack.

### Exit Criteria
- Local server runs and streams events.
- UI works without external infra.
- Presets + tool packs work with CLI and server.

---

## Phase 2: Developer Experience and Reliability (4-6 weeks)

### Objective
Make the platform feel production-grade for developers (not full SaaS yet).

### 2.1 Observability Upgrade
- Structured run logs (JSON lines).
- Metrics: latency, token usage, tool error rates.
- Exporter interface (stdout + file).

### 2.2 Testing Harness
- Add deterministic mock LLM and tool mocks.
- Regression tests for tool schemas.
- Golden test for streaming event order.

### 2.3 Memory and RAG
- Built-in vector store adapter (SQLite or local embedding service).
- Memory compaction policies.
- Pluggable embedding provider.

### Exit Criteria
- Coverage on core runtime paths.
- Basic memory/RAG workflow in presets.

---

## Phase 3: Platform Extensions (optional, 6-10 weeks)

### Objective
Introduce features that start resembling OpenClaw-level platform capabilities.

### 3.1 Gateway Mode (optional)
- WebSocket protocol for streaming and multi-client access.
- Device/agent registration.

### 3.2 Channel Integrations (optional)
- Slack/Discord/Web UI connectors.

### 3.3 Multi-tenant readiness
- Org/user scoping, quota management.
- Storage layer upgraded to Postgres.

### Exit Criteria
- At least one channel integration works end-to-end.
- Multi-tenant design doc complete.

---

## Implementation Matrix (SDK vs Platform)

SDK owns:
- agent loop semantics
- tool lifecycle + schemas
- model routing + retries
- memory primitives + compaction
- event streams + observability hooks
- preset definitions + tool packs

Platform owns:
- UI surfaces
- API gateway semantics
- storage infra and scaling
- deployment and ops
- user/org management

---

## Suggested Repo Layout

agent-sdk/
  agent_sdk/
    runtime/
    tools/
    presets/
    storage/
    server/
    ui/
  documents/
    BATTERY_INCLUDED_PLATFORM_PLAN.md

---

## Risks and Mitigations
- Risk: scope creep into full SaaS.
  - Mitigation: enforce platform boundary and keep Phase 1 local-only.
- Risk: tool schema churn.
  - Mitigation: semantic versioning of tool schemas.
- Risk: streaming complexity.
  - Mitigation: define strict event envelopes early.

---

## Next Steps (actionable)
- Kick off Phase 4 with org scoping + RBAC enforcement.
- Implement Postgres event persistence + replay endpoints.
- Add retention policies + audit logs + quota enforcement.

---

## Phase 1 Backlog (Prioritized, Rough Estimates)

1. Define event envelope schema (`assistant`, `tool`, `lifecycle`) and run/session metadata model. **(Completed)**  
Estimate: 2-3 days.

2. Implement run/session IDs and metadata propagation across planner/executor runtime. **(Completed)**  
Estimate: 2-3 days.

3. Add storage interface for runs/sessions + default local SQLite adapter (optional in config). **(Completed)**  
Estimate: 3-5 days.

4. Implement SSE streaming in FastAPI (`/run/{id}/events`) with backpressure safeguards. **(Completed)**  
Estimate: 3-4 days.

5. Add `POST /run`, `GET /run/{id}`, `GET /sessions`, `GET /sessions/{id}` endpoints. **(Completed)**  
Estimate: 3-4 days.

6. Basic API key auth middleware + config validation at server startup. **(Completed)**  
Estimate: 1-2 days.

7. Build minimal dev console UI (submit prompt, stream output, show tool calls). **(Completed)**  
Estimate: 4-6 days.

8. Serve UI from server root (`/`) and add static build step. **(Completed)**  
Estimate: 1-2 days.

9. Implement presets (`assistant_basic`, `assistant_tools`, `assistant_rag`, `assistant_multiagent`). **(Completed)**  
Estimate: 2-3 days.

10. Build tool packs with schema + metadata, auto-load builtin tools. **(Completed)**  
Estimate: 4-6 days.

11. CLI wiring for presets and local server launch (`agent-sdk run --preset ...`, `agent-sdk server`). **(Completed)**  
Estimate: 2-3 days.

12. Regression tests: event ordering, SSE stream, tool schema validation. **(Completed)**  
Estimate: 3-5 days.

---

## Phase 2 Backlog (Prioritized, Rough Estimates)

1. Observability upgrade: structured JSONL run logs + exporter interface (stdout/file). **(Completed)**  
Estimate: 3-5 days.

2. Metrics pipeline: latency, token usage, tool error rates (collector + emitters). **(Completed)**  
Estimate: 3-4 days.

3. Deterministic mock LLM + tool mocks for tests. **(Completed)**  
Estimate: 3-4 days.

4. Streaming regression tests (ordering, replay, disconnect handling). **(Completed)**  
Estimate: 3-5 days.

5. Tool schema regression tests (validation + versioning). **(Completed)**  
Estimate: 2-3 days.

6. Memory compaction policies (configurable thresholds + summarization hooks). **(Completed)**  
Estimate: 4-6 days.

7. Local vector store adapter (SQLite or embedded) + embedding provider interface. **(Completed)**  
Estimate: 5-8 days.

8. RAG preset improvements (end-to-end retrieval + citation metadata). **(Completed)**  
Estimate: 3-5 days.

9. CLI diagnostics: `agent-sdk doctor` for config/health checks. **(Completed)**  
Estimate: 2-3 days.

10. Dev UX polish: consistent error messages + actionable hints. **(Completed)**  
Estimate: 2-3 days.

---

## Phase 3 Backlog (Prioritized, Rough Estimates)

1. Gateway mode design + protocol spec (WebSocket event envelopes, auth, reconnect). **(Completed)**  
Estimate: 4-6 days.

2. Gateway server skeleton: WS server with connect/auth, run stream proxying. **(Completed)**  
Estimate: 6-10 days.

3. Multi-client support: subscriptions + backpressure control. **(Completed)**  
Estimate: 4-6 days.

4. Device/agent registration model (identity + pairing flow). **(Completed)**  
Estimate: 5-8 days.

5. First channel integration (pick one: Slack/Discord/Web) with end-to-end flow. **(Completed)**  
Estimate: 2-3 weeks.

6. Multi-tenant data model (org/user scoping + quotas) and storage upgrade plan. **(Completed)**  
Estimate: 2-3 weeks.

7. Postgres storage adapter (runs/sessions/events). **(Completed)**  
Estimate: 1-2 weeks.

8. Admin UI basics (orgs, API keys, usage overview). **(Completed)**  
Estimate: 2-3 weeks.

9. Deployment blueprint: Docker Compose + minimal production guide. **(Completed)**  
Estimate: 3-5 days.

---

## Phase 4: Production Hardening (optional, 8-14 weeks)

### Objective
Make the SDK safe, scalable, and governable for customers building platforms on top of agent-sdk.

### 4.1 Security and Access Control
- Enforce org scoping on all run/session/event access paths.
- Add RBAC + token scopes (admin/developer/viewer).
- Tool sandboxing and allowlist enforcement for filesystem/http tools.
- Secrets management integration (env + file + vault-ready interface).

Deliverables:
- `agent_sdk/security` RBAC + scope middleware.
- `agent_sdk/tools` sandbox policy and allowlist config.
- Docs: Security model + least-privilege guidance.

### 4.2 Durability and Replay
- Persist run events to Postgres and support replay from storage.
- Retention policies and archiving.
- Run state recovery for in-flight runs after restart.

Deliverables:
- `agent_sdk/storage/postgres` events persistence with replay.
- Run event retention policy config.
- Replay endpoints for SSE/WS.

### 4.3 Governance and Compliance
- Data retention + deletion APIs.
- Audit logs for admin actions and API key changes.
- PII redaction pipeline for logs/events.

Deliverables:
- `agent_sdk/observability/audit_logs`.
- Admin APIs for retention and deletion.
- PII redaction configuration and tests.

### 4.4 Model Management and Policy
- Per-tenant model registry and fallback routing policies.
- Cost and token caps per org/user.
- Prompt/policy versioning for safety controls.

Deliverables:
- `agent_sdk/llm` tenant registry + policy router.
- Quota enforcement on run start and tool usage.
- Prompt policy registry + versioning docs.

### 4.5 Reliability and Scaling
- Queue-based execution option (worker pool).
- Backpressure propagation across tools and streams.
- Retry policies and idempotency keys for runs.

Deliverables:
- Task queue interface + local worker implementation.
- Backpressure + retry policy config.
- Idempotency support on run creation.

### 4.6 Platform DX and Ops
- Production deployment guide (TLS, proxies, backups, migrations).
- Migration tooling for schema upgrades.
- Reference multi-tenant demo app and integration guide.

Deliverables:
- `docs/PRODUCTION_HARDENING.md` and migration runbook.
- `docs/PLATFORM_BUILDER_GUIDE.md`.
- Example reference app using the SDK.

### Exit Criteria
- Org scoping and RBAC enforced across API + storage.
- Postgres event persistence with replay verified.
- Quotas, audit logs, and retention policies enforced.
- Production deployment guide published and validated.

---

## Phase 4 Backlog (Prioritized, Rough Estimates)

1. Enforce org scoping across API + storage (runs/sessions/events). **(Completed)**  
Estimate: 1-2 weeks.

2. RBAC + token scopes (admin/developer/viewer). **(Completed)**  
Estimate: 1-2 weeks.

3. Tool sandboxing + allowlists for filesystem/http tools. **(Completed)**  
Estimate: 1-2 weeks.

4. Secrets management interface (env + file + vault-ready). **(Completed)**  
Estimate: 3-5 days.

5. Postgres event persistence + replay endpoints (SSE/WS). **(Completed)**  
Estimate: 1-2 weeks.

6. Retention policies + archiving for run events. **(Completed)**  
Estimate: 3-5 days.

7. Run recovery for in-flight runs after restart. **(Completed)**  
Estimate: 3-5 days.

8. Audit logs for admin actions and API key changes. **(Completed)**  
Estimate: 3-5 days.

9. Data retention + deletion APIs.  
Estimate: 1 week.

10. PII redaction pipeline for logs/events.  
Estimate: 3-5 days.

11. Per-tenant model registry + fallback policies.  
Estimate: 1-2 weeks.

12. Quota enforcement for tokens/runs/sessions.  
Estimate: 1 week.

13. Prompt/policy versioning for safety controls.  
Estimate: 3-5 days.

14. Queue-based execution option + worker pool.  
Estimate: 1-2 weeks.

15. Backpressure propagation + retry policy config.  
Estimate: 1 week.

16. Idempotency keys for run creation.  
Estimate: 3-5 days.

17. Production deployment guide (TLS, proxies, backups, migrations).  
Estimate: 1 week.

18. Migration tooling and runbook.  
Estimate: 3-5 days.

19. Platform builder guide + reference multi-tenant demo app.  
Estimate: 1-2 weeks.

---

## Phase 4 Validation Criteria
- RBAC and org scoping enforced in tests for all endpoints and storage queries.
- Event replay validated against Postgres storage with retention policy applied.
- Quotas enforced with clear error responses and audit log entries.
- Deployment guide verified with a Docker Compose smoke test.
