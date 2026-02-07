"""Tests for secrets manager providers."""

import json
import os
import tempfile

from agent_sdk.secrets import FileSecretsProvider, SecretsManager, EnvSecretsProvider


def test_file_secrets_provider_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "secrets.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"API_KEY": "file-key"}, f)
        provider = FileSecretsProvider(path=path)
        assert provider.get("API_KEY") == "file-key"


def test_secrets_manager_env_precedence(monkeypatch):
    manager = SecretsManager([EnvSecretsProvider()])
    monkeypatch.setenv("API_KEY", "env-key")
    assert manager.get("API_KEY") == "env-key"
