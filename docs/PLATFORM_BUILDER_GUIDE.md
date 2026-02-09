# Platform Builder Guide

This guide shows how to build a multi-tenant platform on top of agent-sdk.

## Architecture
- Agent runtime: `agent_sdk` (planner/executor + tools).
- Platform services: API server, storage, UI, and integrations.
- Governance: org scoping, RBAC, quotas, audit logs.

## Quick Start (Local)
1. Configure `config.yaml` with your models/agents.
2. Start the server: `python -m agent_sdk.server.app`.
3. Create an admin API key and configure org policies.

## Multi-Tenant Basics
- Send `X-Org-Id` for all requests.
- Create org API keys via `/admin/api-keys`.
- Configure per-tenant quotas and model policies.

## Operations
- Enable audit logging.
- Enable PII redaction.
- Use Postgres for production persistence.

## Example App
See `examples/multi_tenant_demo` for a reference setup.
