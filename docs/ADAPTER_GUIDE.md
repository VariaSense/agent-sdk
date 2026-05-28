# Adapter Guide

## Purpose

This guide defines how applications and infrastructure integrations should plug into `agent-sdk` after the boundary refactor.

## Public Port Modules

Use these modules as the stable dependency inversion surface:

- `agent_sdk.ports`
- `agent_sdk.contracts`
- `agent_sdk.runtime.ExternalAgentRuntime`

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

## Third-Party Agent CLIs

Use `ExternalAgentRuntime` to wrap local agent CLIs, including Codex-style engineering agents,
behind the stable `AgentRuntimePort`.

```python
from agent_sdk.contracts import AgentDefinition, RunRequest
from agent_sdk.runtime import ExternalAgentRuntime

runtime = ExternalAgentRuntime.codex(cwd="/path/to/workspace")
result = runtime.run(
    RunRequest(
        agent=AgentDefinition(name="codex-worker", model="gpt-5"),
        prompt="Implement the assigned task and summarize the result.",
    )
)
```

For non-Codex agents, create an `ExternalAgentCommand` with an executable, argument list,
working directory, timeout, prompt mode, and output format. The SDK runs the command without
a shell and maps stdout, stderr, JSONL events, status, and metadata into `RunResult`.

The Codex factory defaults to `--ignore-user-config` so SDK-launched workers use the prompt
and runtime contract supplied by the embedding application instead of a developer's local
Codex configuration.

## Current Example

`agent-platform` integrates with SDK runtime through:

- `agent_sdk.contracts`
- `agent_sdk.runtime.EmbeddedAgentRunner`

Its platform adapter is:

- `agent_platform.sdk_runtime.SDKRuntimeAdapter`
