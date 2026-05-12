"""Service ports re-exported as stable SDK integration points."""

from agent_sdk.interfaces.contracts import (
    IdentityProviderContract,
    LLMClientContract,
    PolicyRegistryContract,
    SecretsProviderContract,
    StorageContract,
    ToolCallableContract,
    WebhookSenderContract,
)

LLMClientPort = LLMClientContract
ToolCallablePort = ToolCallableContract
StoragePort = StorageContract
IdentityProviderPort = IdentityProviderContract
SecretsProviderPort = SecretsProviderContract
WebhookSenderPort = WebhookSenderContract
PolicyRegistryPort = PolicyRegistryContract

__all__ = [
    "LLMClientPort",
    "ToolCallablePort",
    "StoragePort",
    "IdentityProviderPort",
    "SecretsProviderPort",
    "WebhookSenderPort",
    "PolicyRegistryPort",
]
