# Public Contracts

## Purpose

This document freezes the minimal public SDK integration surface for the current refactor phase.

Applications such as `agent-platform` are expected to depend on these contracts instead of reaching into internal SDK implementation modules.

## Contract Version

Current version:

- `v1`

The `v1` marker is encoded directly in the runtime contract models under `agent_sdk.contracts.runtime`.

## Public SDK Modules

The following modules are currently treated as public integration surface:

- `agent_sdk.contracts`
- `agent_sdk.interfaces`
- `agent_sdk.ports`
- `agent_sdk.runtime`
- `agent_sdk.core.runtime`
- `agent_sdk.core.messages`
- `agent_sdk.config.model_config`

Everything else should be treated as internal unless explicitly documented otherwise.

## Public Runtime Models

Defined in `agent_sdk.contracts.runtime`:

- `AgentDefinition`
- `ExecutionMetadata`
- `RunRequest`
- `RunEvent`
- `RunResult`
- `AgentRuntimeContract`

## Public Support Ports

- `EventPublisherPort`
- `ToolRegistryPort`
- `MemoryRepositoryPort`
- `LLMClientPort`
- `ToolCallablePort`
- `StoragePort`
- `IdentityProviderPort`
- `SecretsProviderPort`
- `WebhookSenderPort`
- `PolicyRegistryPort`

## Compatibility Rules

1. `contract_version="v1"` must remain stable for backward-compatible changes.
2. New fields may be added only when they are optional or have safe defaults.
3. Existing field names and meanings must not change within `v1`.
4. Removing or renaming a field requires a new contract version.
5. Platform code should consume these DTOs directly or through a platform adapter.

## Integration Rule

Applications embedding the SDK should instantiate a public runtime entrypoint such as:

- `agent_sdk.runtime.EmbeddedAgentRunner`

They should not reconstruct runtime behavior by importing an arbitrary mix of planner, executor, server, or storage internals unless that integration is explicitly owned by the SDK API.
