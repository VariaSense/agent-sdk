# Deprecation Policy

## Purpose

This document records the transitional policy for SDK surfaces that are being removed from platform ownership.

## Policy

1. When a module stops being SDK-owned, the SDK keeps a compatibility shim for at least one refactor phase.
2. Compatibility shims emit `DeprecationWarning` at use time.
3. The warning message must point to the new canonical module or package.
4. New product features must not be added to deprecated SDK shims.
5. Platform-owned replacements should receive all new behavior.

## Current Deprecated SDK Shims

- `agent_sdk.billing` -> `agent_platform.chargeback`
- `agent_sdk.privacy` -> `agent_platform.privacy`
- `agent_sdk.webhooks` -> `agent_platform.webhooks`
- `agent_sdk.server.app` -> `agent_platform.hosted_api`
- `agent_sdk.server.admin_ui` -> `agent_platform.admin_ui`
- `agent_sdk.server.multi_tenant` -> `agent_platform.tenant_store`
- `agent_sdk.storage.control_plane` -> `agent_platform.control_plane`
- `agent_sdk.dashboard.server` -> `agent_platform.dashboard`
