"""Tests for cloud secrets providers wiring."""

import os

from agent_sdk.secrets import (
    AWSSecretsManagerProvider,
    GCPSecretManagerProvider,
    AzureKeyVaultProvider,
    default_secrets_manager,
)


def test_aws_secrets_provider_added(monkeypatch):
    monkeypatch.setenv("AGENT_SDK_AWS_SECRETS_ENABLED", "true")
    monkeypatch.setenv("AGENT_SDK_AWS_REGION", "us-east-1")
    manager = default_secrets_manager()
    assert any(isinstance(p, AWSSecretsManagerProvider) for p in manager.providers)


def test_gcp_secrets_provider_added(monkeypatch):
    monkeypatch.setenv("AGENT_SDK_GCP_PROJECT_ID", "demo-project")
    manager = default_secrets_manager()
    assert any(isinstance(p, GCPSecretManagerProvider) for p in manager.providers)


def test_azure_secrets_provider_added(monkeypatch):
    monkeypatch.setenv("AGENT_SDK_AZURE_KEYVAULT_URL", "https://vault.example.vault.azure.net/")
    manager = default_secrets_manager()
    assert any(isinstance(p, AzureKeyVaultProvider) for p in manager.providers)
