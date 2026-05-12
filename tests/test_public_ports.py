from agent_sdk.ports import (
    AgentRuntimePort,
    EventPublisherPort,
    IdentityProviderPort,
    LLMClientPort,
    MemoryRepositoryPort,
    PolicyRegistryPort,
    SecretsProviderPort,
    StoragePort,
    ToolRegistryPort,
    ToolCallablePort,
    WebhookSenderPort,
)
from agent_sdk.runtime import EmbeddedAgentRunner


def test_embedded_runner_satisfies_runtime_port():
    runner = EmbeddedAgentRunner()
    assert isinstance(runner, AgentRuntimePort)


def test_public_ports_are_exported():
    exported = {
        AgentRuntimePort,
        EventPublisherPort,
        IdentityProviderPort,
        LLMClientPort,
        MemoryRepositoryPort,
        PolicyRegistryPort,
        SecretsProviderPort,
        StoragePort,
        ToolRegistryPort,
        ToolCallablePort,
        WebhookSenderPort,
    }
    assert len(exported) == 11
