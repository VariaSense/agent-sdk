# Phase 3 Multi-Tenant Readiness Plan

## Goals
- Introduce organization and user scoping for runs, sessions, and API keys.
- Add quota controls to protect shared infrastructure.
- Define a migration path from local storage to Postgres.

## Data Model (v0)
- Organization
  - `org_id`, `name`, `created_at`
  - `quotas`: `max_runs_per_day`, `max_tokens_per_day`, `max_sessions_per_day`
- User
  - `user_id`, `org_id`, `name`, `created_at`
- API Key
  - `key_id`, `org_id`, `label`, `created_at`, `active`
- Usage Summary
  - `org_id`, `run_count`, `session_count`, `last_run_at`, `last_session_at`

## Scope Rules
- Every run/session is associated with an `org_id`.
- API keys are scoped to a single org.
- Default org is `default` for local-first installs.
- `X-Org-Id` header enables explicit scoping in requests.

## Quota Enforcement Plan
1. Track usage counters per org (runs, sessions, tokens).
2. Enforce hard limits at request start:
   - Reject on quota exhaustion with actionable error.
3. Add soft-limit warnings for approaching caps.
4. Provide admin overrides for internal testing.

## Migration to Postgres
- Keep the SDK runtime stable, move platform data to Postgres.
- Add a `PostgresStorage` adapter for runs/sessions/events.
- Add a `tenants` schema for org/user/key tables.
- Use migrations to evolve schema without data loss.

## Open Questions
- Quota granularity (per-user vs per-org).
- Token accounting precision for multi-agent runs.
- Audit log requirements for admin actions.
