"""Tests for local tool registry."""

import os
import tempfile

from agent_sdk.registry.local import LocalRegistry
from agent_sdk.tool_packs.manifest import ToolManifest


def test_local_registry_publish_and_pull():
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = LocalRegistry(root=tmpdir)
        manifest = ToolManifest(
            name="utilities",
            version="1.0.0",
            tools=["filesystem.read", "http.fetch"],
            metadata={"description": "test"},
        )
        registry.publish(manifest)

        pulled = registry.pull("utilities", "1.0.0")
        assert pulled.name == "utilities"
        assert pulled.version == "1.0.0"
        assert "filesystem.read" in pulled.tools

        manifests = registry.list_manifests()
        assert any(m.name == "utilities" for m in manifests)
