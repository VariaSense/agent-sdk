# Adapter Guide

## Purpose

This guide defines how applications and infrastructure integrations should plug into `agent-sdk` after the boundary refactor.

## Public Port Modules

Use these modules as the stable dependency inversion surface:

- `agent_sdk.ports`
- `agent_sdk.contracts`

## Available Ports

- `AgentRuntimePort`
- `EventPublisherPort`
- `LLMClientPort`
- `MemoryRepositoryPort`
- `ToolRegistryPort`
- `ToolCallablePort`
- `StoragePort`
- `IdentityProviderPort`
- `SecretsProviderPort`
- `WebhookSenderPort`
- `PolicyRegistryPort`

## Rules

1. New infrastructure adapters should implement a port, not change core runtime code directly.
2. Application code should wire concrete adapters at composition time.
3. SDK runtime entrypoints should accept or build collaborators through ports.
4. Product-specific workflows should not be added to the SDK as new ports unless they are truly reusable.

## Current Example

`agent-platform` integrates with SDK runtime through:

- `agent_sdk.contracts`
- `agent_sdk.runtime.EmbeddedAgentRunner`

Its platform adapter is:

- `agent_platform.sdk_runtime.SDKRuntimeAdapter`
