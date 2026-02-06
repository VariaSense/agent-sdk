"""
Tests for preset registry.
"""

import pytest

from agent_sdk.presets import list_presets, get_preset, get_preset_config


def test_list_presets_contains_expected():
    presets = list_presets()
    names = {p.name for p in presets}
    assert {"assistant_basic", "assistant_tools", "assistant_rag", "assistant_multiagent"} <= names


def test_get_preset_config_shape():
    config = get_preset_config("assistant_basic")
    assert config["name"] == "assistant_basic"
    assert "model" in config
    assert "tool_packs" in config
    assert "memory" in config


def test_get_preset_unknown_raises():
    with pytest.raises(KeyError):
        get_preset("missing")
