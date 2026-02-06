"""
Preset registry for agent-sdk.
"""

from __future__ import annotations

from typing import Dict, List

from agent_sdk.presets.builtin import PRESETS, PresetDefinition


def list_presets() -> List[PresetDefinition]:
    return list(PRESETS.values())


def get_preset(name: str) -> PresetDefinition:
    if name not in PRESETS:
        raise KeyError(f"Preset '{name}' not found")
    return PRESETS[name]


def get_preset_config(name: str) -> Dict[str, object]:
    preset = get_preset(name)
    return {
        "name": preset.name,
        "description": preset.description,
        "model": preset.model,
        "tool_packs": preset.tool_packs,
        "memory": preset.memory,
    }


__all__ = [
    "PresetDefinition",
    "list_presets",
    "get_preset",
    "get_preset_config",
]
