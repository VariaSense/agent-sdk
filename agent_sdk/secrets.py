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
    return SecretsManager(providers)
