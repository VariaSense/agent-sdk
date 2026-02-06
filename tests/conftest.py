"""Test suite for Agent SDK - Shared fixtures and configuration"""

import hashlib
import random
import sys
import types
from typing import Iterable

import pytest
from agent_sdk import AgentContext, Tool, GLOBAL_TOOL_REGISTRY
from agent_sdk.config.model_config import ModelConfig
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.observability.bus import EventBus


@pytest.fixture
def mock_llm():
    """Fixture providing MockLLMClient"""
    return MockLLMClient()

@pytest.fixture(scope="session", autouse=True)
def _mock_sentence_transformers():
    """Provide a lightweight SentenceTransformer for tests.

    This avoids model downloads and heavy initialization while keeping
    deterministic embeddings for assertions.
    """
    try:
        import numpy as np
    except Exception:  # pragma: no cover - numpy is a test dependency
        return

    def _hash_seed(text: str) -> int:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return int(digest[:16], 16)

    def _embed_text(text: str, dim: int) -> list[float]:
        # Hashed bag-of-words with stopword removal for stable similarity.
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "is",
            "are",
            "was",
            "were",
            "to",
            "of",
            "in",
            "on",
            "for",
            "with",
            "as",
            "at",
            "by",
            "from",
            "also",
            "over",
            "jumps",
            "lazy",
            "dog",
        }
        tokens = [
            t
            for t in __import__("re").findall(r"[a-z0-9]+", text.lower())
            if t and t not in stopwords
        ]
        if not tokens:
            return [0.0] * dim

        vector = [0.0] * dim
        for token in tokens:
            token_seed = _hash_seed(token)
            idx = token_seed % dim
            # Deterministic sign to reduce collision bias
            sign = 1.0 if (token_seed >> 1) & 1 else -1.0
            vector[idx] += sign

        # Normalize
        norm = sum(v * v for v in vector) ** 0.5
        if norm == 0.0:
            return vector
        return [v / norm for v in vector]

    class _FakeSentenceTransformer:
        def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
            if "mpnet" in model_name:
                self._dim = 768
            else:
                self._dim = 384
            self.model_name = model_name

        def get_sentence_embedding_dimension(self) -> int:
            return self._dim

        def encode(self, inputs, convert_to_tensor: bool = False):
            if isinstance(inputs, str):
                return np.array(_embed_text(inputs, self._dim))
            if isinstance(inputs, Iterable):
                vectors = [_embed_text(text, self._dim) for text in inputs]
                return np.array(vectors)
            return np.array([])

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = _FakeSentenceTransformer
    sys.modules["sentence_transformers"] = module


@pytest.fixture
def model_config():
    """Fixture providing default ModelConfig"""
    return ModelConfig(
        name="test-gpt4",
        provider="openai",
        model_id="gpt-4",
        temperature=0.7,
        max_tokens=2048
    )


@pytest.fixture
def agent_context(model_config):
    """Fixture providing AgentContext with defaults"""
    return AgentContext(
        tools={},
        model_config=model_config,
        events=None,
        rate_limiter=None,
        max_short_term=100,
        max_long_term=1000
    )


@pytest.fixture
def event_bus():
    """Fixture providing EventBus"""
    return EventBus([])


@pytest.fixture
def sample_tool():
    """Fixture providing a sample echo tool"""
    tool = Tool(
        name="test_echo",
        description="Echo back input",
        func=lambda args: args.get("text", "")
    )
    GLOBAL_TOOL_REGISTRY.register(tool)
    yield tool
    # Cleanup
    if tool.name in GLOBAL_TOOL_REGISTRY.tools:
        del GLOBAL_TOOL_REGISTRY.tools[tool.name]
