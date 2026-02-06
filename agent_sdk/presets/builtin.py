"""
Built-in presets for common agent configurations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class PresetDefinition:
    name: str
    description: str
    model: Dict[str, object]
    tool_packs: List[str]
    memory: Dict[str, object]


PRESETS = {
    "assistant_basic": PresetDefinition(
        name="assistant_basic",
        description="Simple assistant with minimal tooling and memory.",
        model={
            "name": "default",
            "provider": "openai",
            "model_id": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 1024,
        },
        tool_packs=["core"],
        memory={"max_short_term": 200, "max_long_term": 2000},
    ),
    "assistant_tools": PresetDefinition(
        name="assistant_tools",
        description="Tool-using assistant with expanded tool pack.",
        model={
            "name": "default",
            "provider": "openai",
            "model_id": "gpt-4",
            "temperature": 0.2,
            "max_tokens": 2048,
        },
        tool_packs=["core", "utilities"],
        memory={"max_short_term": 400, "max_long_term": 4000},
    ),
    "assistant_rag": PresetDefinition(
        name="assistant_rag",
        description="Retrieval-augmented assistant with semantic memory.",
        model={
            "name": "default",
            "provider": "openai",
            "model_id": "gpt-4",
            "temperature": 0.2,
            "max_tokens": 2048,
        },
        tool_packs=["core", "rag"],
        memory={
            "max_short_term": 400,
            "max_long_term": 8000,
            "rag": {
                "enabled": True,
                "vector_store": "sqlite",
                "embedding_provider": "mock",
                "include_citations": True,
            },
        },
    ),
    "assistant_multiagent": PresetDefinition(
        name="assistant_multiagent",
        description="Multi-agent setup with coordination defaults.",
        model={
            "name": "default",
            "provider": "openai",
            "model_id": "gpt-4",
            "temperature": 0.2,
            "max_tokens": 2048,
        },
        tool_packs=["core", "utilities", "coordination"],
        memory={"max_short_term": 300, "max_long_term": 3000},
    ),
}
