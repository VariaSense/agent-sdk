"""
Tool packs and metadata registry.
"""

from __future__ import annotations

from typing import Dict, Any

from agent_sdk.tool_packs.builtin import TOOL_PACKS, register_builtin_tool_packs


GLOBAL_TOOL_METADATA: Dict[str, Dict[str, Any]] = {}


def load_builtin_tool_packs() -> None:
    register_builtin_tool_packs(metadata_registry=GLOBAL_TOOL_METADATA)


__all__ = [
    "TOOL_PACKS",
    "GLOBAL_TOOL_METADATA",
    "register_builtin_tool_packs",
    "load_builtin_tool_packs",
]
