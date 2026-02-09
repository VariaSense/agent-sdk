"""
Tool packs and metadata registry.
"""

from __future__ import annotations

from typing import Dict, Any, Optional

from agent_sdk.tool_packs.builtin import TOOL_PACKS, TOOL_PACK_VERSIONS, register_builtin_tool_packs
from agent_sdk.tool_packs.manifest import ToolManifest, sign_manifest, default_manifest_secret


GLOBAL_TOOL_METADATA: Dict[str, Dict[str, Any]] = {}


def load_builtin_tool_packs() -> None:
    register_builtin_tool_packs(metadata_registry=GLOBAL_TOOL_METADATA)


def build_tool_pack_manifest(pack_name: str, version: Optional[str] = None) -> ToolManifest:
    tools = TOOL_PACKS.get(pack_name, [])
    resolved_version = version or TOOL_PACK_VERSIONS.get(pack_name, "1.0.0")
    manifest = ToolManifest(name=pack_name, version=resolved_version, tools=tools)
    secret = default_manifest_secret()
    if secret:
        return sign_manifest(manifest, secret)
    return manifest


__all__ = [
    "TOOL_PACKS",
    "GLOBAL_TOOL_METADATA",
    "register_builtin_tool_packs",
    "load_builtin_tool_packs",
    "build_tool_pack_manifest",
]
