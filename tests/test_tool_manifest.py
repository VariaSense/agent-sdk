"""Tests for tool pack manifests."""

import os

from agent_sdk.tool_packs.manifest import ToolManifest, sign_manifest, verify_manifest
from agent_sdk.tool_packs import build_tool_pack_manifest


def test_manifest_sign_and_verify(monkeypatch):
    secret = "secret"
    manifest = ToolManifest(name="core", version="1.0.0", tools=["a", "b"])
    signed = sign_manifest(manifest, secret)
    assert signed.signature
    assert verify_manifest(signed, secret)


def test_build_manifest_with_env_secret(monkeypatch):
    monkeypatch.setenv("AGENT_SDK_TOOL_MANIFEST_SECRET", "secret")
    manifest = build_tool_pack_manifest("core", version="1.0.0")
    assert manifest.signature
