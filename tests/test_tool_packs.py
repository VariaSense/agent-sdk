"""
Tests for tool pack loading and metadata.
"""

from agent_sdk.core.tools import GLOBAL_TOOL_REGISTRY
from agent_sdk.tool_packs import TOOL_PACKS, GLOBAL_TOOL_METADATA, load_builtin_tool_packs


def test_tool_packs_loaded():
    load_builtin_tool_packs()
    assert "core" in TOOL_PACKS
    assert "utilities" in TOOL_PACKS

    # Check a sample tool
    assert "calculator" in GLOBAL_TOOL_REGISTRY.tools
    assert "calculator" in GLOBAL_TOOL_METADATA
    assert "schema" in GLOBAL_TOOL_METADATA["calculator"]


def test_all_tool_metadata_has_schema():
    load_builtin_tool_packs()
    for name, meta in GLOBAL_TOOL_METADATA.items():
        assert "schema" in meta
        assert meta["schema"].get("name") == name
