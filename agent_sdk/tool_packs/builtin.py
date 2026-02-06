"""
Built-in tool packs with schema metadata.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List
from urllib.request import Request, urlopen

from agent_sdk.core.tools import Tool, ToolRegistry, GLOBAL_TOOL_REGISTRY


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    func: Callable[[Dict[str, Any]], Any]
    schema: Dict[str, Any]


def _filesystem_read(inputs: Dict[str, Any]) -> str:
    path = inputs.get("path")
    if not path:
        raise ValueError("path is required")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _filesystem_write(inputs: Dict[str, Any]) -> str:
    path = inputs.get("path")
    content = inputs.get("content", "")
    if not path:
        raise ValueError("path is required")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return "ok"


def _http_fetch(inputs: Dict[str, Any]) -> str:
    url = inputs.get("url")
    if not url:
        raise ValueError("url is required")
    req = Request(url, headers={"User-Agent": "agent-sdk"})
    with urlopen(req, timeout=10) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="replace")


def _calculator(inputs: Dict[str, Any]) -> float:
    op = inputs.get("operation")
    a = float(inputs.get("a", 0))
    b = float(inputs.get("b", 0))
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    if op == "div":
        return a / b
    raise ValueError("operation must be one of add|sub|mul|div")


def _time_utc(_: Dict[str, Any]) -> str:
    return datetime.now(timezone.utc).isoformat()


def _vector_search_stub(inputs: Dict[str, Any]) -> str:
    query = inputs.get("query", "")
    return f"vector search not configured (query={query})"


TOOL_DEFINITIONS: Dict[str, ToolDefinition] = {
    "filesystem.read": ToolDefinition(
        name="filesystem.read",
        description="Read a UTF-8 file from disk.",
        func=_filesystem_read,
        schema={
            "name": "filesystem.read",
            "inputs": {"path": "string"},
            "outputs": "string",
        },
    ),
    "filesystem.write": ToolDefinition(
        name="filesystem.write",
        description="Write a UTF-8 file to disk.",
        func=_filesystem_write,
        schema={
            "name": "filesystem.write",
            "inputs": {"path": "string", "content": "string"},
            "outputs": "string",
        },
    ),
    "http.fetch": ToolDefinition(
        name="http.fetch",
        description="Fetch a URL via HTTP GET.",
        func=_http_fetch,
        schema={
            "name": "http.fetch",
            "inputs": {"url": "string"},
            "outputs": "string",
        },
    ),
    "calculator": ToolDefinition(
        name="calculator",
        description="Basic arithmetic operations.",
        func=_calculator,
        schema={
            "name": "calculator",
            "inputs": {"operation": "string", "a": "number", "b": "number"},
            "outputs": "number",
        },
    ),
    "time": ToolDefinition(
        name="time",
        description="Get current UTC timestamp.",
        func=_time_utc,
        schema={"name": "time", "inputs": {}, "outputs": "string"},
    ),
    "vector.search": ToolDefinition(
        name="vector.search",
        description="Search semantic memory (stub).",
        func=_vector_search_stub,
        schema={
            "name": "vector.search",
            "inputs": {"query": "string"},
            "outputs": "string",
        },
    ),
}


TOOL_PACKS: Dict[str, List[str]] = {
    "core": ["calculator", "time"],
    "utilities": ["filesystem.read", "filesystem.write", "http.fetch"],
    "rag": ["vector.search"],
    "coordination": [],
}


def register_builtin_tool_packs(
    registry: ToolRegistry = GLOBAL_TOOL_REGISTRY,
    metadata_registry: Dict[str, Dict[str, Any]] | None = None,
) -> None:
    if metadata_registry is None:
        metadata_registry = {}
    for name, definition in TOOL_DEFINITIONS.items():
        registry.register(Tool(name=definition.name, description=definition.description, func=definition.func))
        metadata_registry[name] = {
            "name": definition.name,
            "description": definition.description,
            "schema": definition.schema,
        }
