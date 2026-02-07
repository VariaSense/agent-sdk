"""
Built-in tool packs with schema metadata.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.request import Request, urlopen

from agent_sdk.core.tools import Tool, ToolRegistry, GLOBAL_TOOL_REGISTRY
from agent_sdk.data_connectors.document import Document
from agent_sdk.memory.embeddings import LocalEmbeddings
from agent_sdk.memory.semantic_memory import MockEmbeddingProvider
from agent_sdk.memory.persistence import SQLiteVectorStore

SCHEMA_VERSION = "1.0"

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


def _run_async(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    return asyncio.run(coro)


def _select_embedder() -> Any:
    provider = os.getenv("AGENT_SDK_VECTOR_EMBEDDINGS", "mock").lower()
    if provider == "local":
        return LocalEmbeddings()
    return MockEmbeddingProvider()


def _cosine_similarity(vec1, vec2) -> float:
    import math
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _vector_search(inputs: Dict[str, Any]) -> Dict[str, Any]:
    query = inputs.get("query", "")
    top_k = int(inputs.get("top_k", 3))
    documents_input = inputs.get("documents")

    if not query:
        raise ValueError("query is required")

    embedder = _select_embedder()
    if isinstance(embedder, LocalEmbeddings):
        query_vec = embedder.embed_text_sync(query)
    else:
        query_vec = embedder.embed(query)

    documents: List[Document] = []
    if documents_input:
        for idx, item in enumerate(documents_input):
            documents.append(
                Document(
                    content=item.get("content", ""),
                    metadata=item.get("metadata", {}),
                    source=item.get("source", "user"),
                    doc_id=item.get("doc_id", f"doc_{idx}"),
                )
            )
    else:
        store_path = os.getenv("AGENT_SDK_VECTOR_DB_PATH", "vector_store.db")
        store = SQLiteVectorStore(store_path)
        doc_ids = _run_async(store.list_all())
        for doc_id in doc_ids:
            loaded = _run_async(store.load(doc_id))
            if loaded:
                documents.append(loaded[0])

    matches = []
    for doc in documents:
        if isinstance(embedder, LocalEmbeddings):
            doc_vec = embedder.embed_text_sync(doc.content)
        else:
            doc_vec = embedder.embed(doc.content)
        score = _cosine_similarity(query_vec, doc_vec)
        matches.append((doc, score))

    matches.sort(key=lambda item: item[1], reverse=True)
    top_matches = matches[:top_k]

    citations = []
    results = []
    for doc, score in top_matches:
        excerpt = doc.content[:160]
        citations.append(
            {
                "doc_id": doc.doc_id,
                "source": doc.source,
                "score": score,
                "excerpt": excerpt,
            }
        )
        results.append(
            {
                "doc_id": doc.doc_id,
                "content": doc.content,
                "metadata": doc.metadata,
                "source": doc.source,
                "score": score,
            }
        )

    return {
        "matches": results,
        "citations": citations,
    }


TOOL_DEFINITIONS: Dict[str, ToolDefinition] = {
    "filesystem.read": ToolDefinition(
        name="filesystem.read",
        description="Read a UTF-8 file from disk.",
        func=_filesystem_read,
        schema={
            "name": "filesystem.read",
            "version": SCHEMA_VERSION,
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
            "version": SCHEMA_VERSION,
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
            "version": SCHEMA_VERSION,
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
            "version": SCHEMA_VERSION,
            "inputs": {"operation": "string", "a": "number", "b": "number"},
            "outputs": "number",
        },
    ),
    "time": ToolDefinition(
        name="time",
        description="Get current UTC timestamp.",
        func=_time_utc,
        schema={"name": "time", "version": SCHEMA_VERSION, "inputs": {}, "outputs": "string"},
    ),
    "vector.search": ToolDefinition(
        name="vector.search",
        description="Search semantic memory (stub).",
        func=_vector_search,
        schema={
            "name": "vector.search",
            "version": SCHEMA_VERSION,
            "inputs": {"query": "string", "top_k": "number", "documents": "array"},
            "outputs": "object",
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
    metadata_registry: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    if metadata_registry is None:
        metadata_registry = {}
    for name, definition in TOOL_DEFINITIONS.items():
        registry.register(Tool(name=definition.name, description=definition.description, func=definition.func))
        metadata_registry[name] = {
            "name": definition.name,
            "description": definition.description,
            "schema": definition.schema,
            "schema_version": definition.schema.get("version", SCHEMA_VERSION),
        }
