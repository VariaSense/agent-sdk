"""Secrets management interface with env + file providers and optional vault integration."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, List

try:
    import yaml
except Exception:  # pragma: no cover - optional
    yaml = None


class SecretsProvider(ABC):
    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        raise NotImplementedError


@dataclass
class EnvSecretsProvider(SecretsProvider):
    def get(self, key: str) -> Optional[str]:
        return os.getenv(key)


@dataclass
class FileSecretsProvider(SecretsProvider):
    path: str
    format: Optional[str] = None

    def _load(self) -> Dict[str, str]:
        if not os.path.exists(self.path):
            return {}
        content = open(self.path, "r", encoding="utf-8").read()
        fmt = (self.format or os.path.splitext(self.path)[1].lstrip(".")).lower()
        if fmt in {"json"}:
            data = json.loads(content or "{}")
        elif fmt in {"yaml", "yml"}:
            if yaml is None:
                raise RuntimeError("pyyaml is required for yaml secrets files")
            data = yaml.safe_load(content) or {}
        else:
            raise ValueError("Unsupported secrets file format")
        return {str(k): str(v) for k, v in data.items()}

    def get(self, key: str) -> Optional[str]:
        data = self._load()
        return data.get(key)


@dataclass
class VaultSecretsProvider(SecretsProvider):
    address: str
    token: str
    mount: str = "secret"

    def get(self, key: str) -> Optional[str]:
        try:
            import hvac  # type: ignore
        except Exception as exc:  # pragma: no cover - optional
            raise RuntimeError("hvac is required for vault secrets") from exc
        client = hvac.Client(url=self.address, token=self.token)
        if not client.is_authenticated():
            raise RuntimeError("Vault authentication failed")
        response = client.secrets.kv.v2.read_secret_version(path=key, mount_point=self.mount)
        data = response.get("data", {}).get("data", {})
        value = data.get(key)
        return str(value) if value is not None else None


@dataclass
class AWSSecretsManagerProvider(SecretsProvider):
    region: Optional[str] = None
    secret_id: Optional[str] = None
    _cache: Dict[str, str] = None

    def _client(self):
        try:
            import boto3  # type: ignore
        except Exception as exc:  # pragma: no cover - optional
            raise RuntimeError("boto3 is required for AWS Secrets Manager") from exc
        return boto3.client("secretsmanager", region_name=self.region)

    def _load_secret_map(self) -> Dict[str, str]:
        if self._cache is None:
            self._cache = {}
        if self.secret_id is None:
            return self._cache
        if self._cache:
            return self._cache
        client = self._client()
        response = client.get_secret_value(SecretId=self.secret_id)
        secret_string = response.get("SecretString") or "{}"
        try:
            data = json.loads(secret_string)
        except json.JSONDecodeError:
            data = {self.secret_id: secret_string}
        self._cache.update({str(k): str(v) for k, v in data.items()})
        return self._cache

    def get(self, key: str) -> Optional[str]:
        if self.secret_id:
            return self._load_secret_map().get(key)
        client = self._client()
        response = client.get_secret_value(SecretId=key)
        value = response.get("SecretString")
        return str(value) if value is not None else None


@dataclass
class GCPSecretManagerProvider(SecretsProvider):
    project_id: str

    def _client(self):
        try:
            from google.cloud import secretmanager  # type: ignore
        except Exception as exc:  # pragma: no cover - optional
            raise RuntimeError("google-cloud-secret-manager is required for GCP secrets") from exc
        return secretmanager.SecretManagerServiceClient()

    def get(self, key: str) -> Optional[str]:
        client = self._client()
        name = f"projects/{self.project_id}/secrets/{key}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("utf-8")
        return payload


@dataclass
class AzureKeyVaultProvider(SecretsProvider):
    vault_url: str

    def _client(self):
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore
            from azure.keyvault.secrets import SecretClient  # type: ignore
        except Exception as exc:  # pragma: no cover - optional
            raise RuntimeError("azure-identity and azure-keyvault-secrets are required") from exc
        credential = DefaultAzureCredential()
        return SecretClient(vault_url=self.vault_url, credential=credential)

    def get(self, key: str) -> Optional[str]:
        client = self._client()
        secret = client.get_secret(key)
        return secret.value


class SecretsManager:
    def __init__(self, providers: List[SecretsProvider]):
        self.providers = providers

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        for provider in self.providers:
            value = provider.get(key)
            if value is not None:
                return value
        return default


def default_secrets_manager() -> SecretsManager:
    providers: List[SecretsProvider] = [EnvSecretsProvider()]
    secrets_file = os.getenv("AGENT_SDK_SECRETS_FILE")
    if secrets_file:
        providers.append(FileSecretsProvider(path=secrets_file, format=os.getenv("AGENT_SDK_SECRETS_FILE_FORMAT")))
    vault_addr = os.getenv("AGENT_SDK_VAULT_ADDR")
    vault_token = os.getenv("AGENT_SDK_VAULT_TOKEN")
    if vault_addr and vault_token:
        providers.append(VaultSecretsProvider(address=vault_addr, token=vault_token))
    aws_enabled = os.getenv("AGENT_SDK_AWS_SECRETS_ENABLED", "").lower() in {"1", "true", "yes", "on"}
    aws_secret_id = os.getenv("AGENT_SDK_AWS_SECRET_ID")
    if aws_enabled or aws_secret_id:
        providers.append(
            AWSSecretsManagerProvider(
                region=os.getenv("AGENT_SDK_AWS_REGION"),
                secret_id=aws_secret_id,
            )
        )
    gcp_project_id = os.getenv("AGENT_SDK_GCP_PROJECT_ID")
    if gcp_project_id:
        providers.append(GCPSecretManagerProvider(project_id=gcp_project_id))
    azure_vault_url = os.getenv("AGENT_SDK_AZURE_KEYVAULT_URL")
    if azure_vault_url:
        providers.append(AzureKeyVaultProvider(vault_url=azure_vault_url))
    return SecretsManager(providers)
