"""Contract tests for interface protocols and mocks."""

from agent_sdk.interfaces import (
    LLMClientContract,
    ToolCallableContract,
    StorageContract,
    IdentityProviderContract,
    SecretsProviderContract,
    WebhookSenderContract,
)
from agent_sdk.testing import DeterministicLLMClient, ToolMock, InMemoryStorage, DummyWebhookSender
from agent_sdk.identity.providers import MockIdentityProvider
from agent_sdk.secrets import EnvSecretsProvider


def test_llm_client_contract():
    client = DeterministicLLMClient(["ok"])
    assert isinstance(client, LLMClientContract)


def test_tool_callable_contract():
    tool = ToolMock(outputs=["ok"])
    assert isinstance(tool, ToolCallableContract)


def test_storage_contract():
    storage = InMemoryStorage()
    assert isinstance(storage, StorageContract)


def test_identity_contract():
    provider = MockIdentityProvider()
    assert isinstance(provider, IdentityProviderContract)


def test_secrets_contract():
    provider = EnvSecretsProvider()
    assert isinstance(provider, SecretsProviderContract)


def test_webhook_sender_contract():
    sender = DummyWebhookSender()
    assert isinstance(sender, WebhookSenderContract)
