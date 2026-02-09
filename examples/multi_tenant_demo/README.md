# Multi-Tenant Demo App

This is a minimal reference app for integrating the Agent SDK with multi-tenant policies.

## What It Shows
- Org-scoped API usage (`X-Org-Id`)
- Admin-managed API keys
- Quotas and model policies

## Running
1. Start the API server with `API_KEY` set.
2. Create org API keys via `/admin/api-keys`.
3. Call `/run` using the org API key and `X-Org-Id`.
