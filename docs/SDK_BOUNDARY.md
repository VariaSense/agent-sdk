# SDK Boundary

## Purpose

`agent-sdk` is the reusable agent execution engine. It is intended to be embedded by applications such as `agent-platform` without pulling in SaaS-specific assumptions.

## SDK Owns

- agent execution lifecycle
- planning and execution primitives
- tool contracts and invocation wrappers
- model provider abstraction
- runtime contracts and event schemas
- generic observability hooks
- generic storage and memory interfaces
- local developer runtime helpers

## SDK Does Not Own

- tenant and org lifecycle
- SaaS billing and entitlements
- hosted deployment promotion workflows
- product admin APIs
- product UI
- customer-specific governance workflows

## Public Integration Surface

External applications should depend on:

- `agent_sdk.contracts`
- `agent_sdk.interfaces`
- `agent_sdk.runtime`

They should avoid depending on internal implementation modules unless those modules are explicitly documented as public.

## Current Refactor Status

- Completed: explicit runtime contracts added under `agent_sdk.contracts`
- Completed: reusable embedded runner added under `agent_sdk.runtime`
- Completed: deprecated compatibility shims added for platform-owned billing/privacy/webhook helpers
- In progress: further reduction of SDK-owned control-plane concerns
