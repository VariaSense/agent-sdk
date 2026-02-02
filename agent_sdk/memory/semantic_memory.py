"""
Semantic Memory with Vector Embeddings

Implements long-term memory with vector embeddings for semantic search,
similarity matching, and contextual retrieval. Supports multiple embedding
models and persistence backends.

Features:
- Vector embeddings (OpenAI, HuggingFace, local models)
- Similarity search and semantic matching
- Memory consolidation and summarization
- Persistence (JSON, SQLite, vector databases)
- Configurable retention and eviction policies
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import json
import logging
import hashlib
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class EmbeddingModel(str, Enum):
    """Supported embedding models."""

    OPENAI_SMALL = "text-embedding-3-small"
    OPENAI_LARGE = "text-embedding-3-large"
    HUGGINGFACE_MINI = "sentence-transformers/all-MiniLM-L6-v2"
    HUGGINGFACE_BASE = "sentence-transformers/all-mpnet-base-v2"
    LOCAL = "local"  # Local sentence-transformers


class MemoryType(str, Enum):
    """Types of memories stored."""

    FACTUAL = "factual"  # Facts learned
    PROCEDURAL = "procedural"  # Procedures/how-to
    EPISODIC = "episodic"  # Events/experiences
    SEMANTIC = "semantic"  # Knowledge/concepts
    TEMPORAL = "temporal"  # Time-related info


class RetentionPolicy(str, Enum):
    """Memory retention policies."""

    INDEFINITE = "indefinite"  # Keep forever
    TIME_BASED = "time_based"  # Remove after X time
    SIZE_LIMITED = "size_limited"  # Keep top N items
    ADAPTIVE = "adaptive"  # Based on relevance


@dataclass
class MemoryItem:
    """
    A single memory item with semantic vector.

    Attributes:
        content: The text content of the memory
        embedding: Vector representation (list of floats)
        memory_type: Type of memory (factual, episodic, etc.)
        created_at: When memory was created
        updated_at: Last access time
        access_count: Number of retrievals
        relevance_score: Current relevance (0-1)
        tags: Metadata tags for filtering
        related_items: IDs of related memories
        summary: Optional condensed version
    """

    content: str
    embedding: List[float]
    memory_type: MemoryType
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    relevance_score: float = 1.0
    tags: List[str] = field(default_factory=list)
    related_items: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    item_id: str = field(default_factory=lambda: None)

    def __post_init__(self):
        """Generate item ID if not provided."""
        if self.item_id is None:
            # Create deterministic ID from content
            self.item_id = hashlib.md5(self.content.encode()).hexdigest()[:8]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_id": self.item_id,
            "content": self.content,
            "embedding": self.embedding,
            "memory_type": self.memory_type.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count,
            "relevance_score": self.relevance_score,
            "tags": self.tags,
            "related_items": self.related_items,
            "summary": self.summary,
        }

    def decay_relevance(self, decay_factor: float = 0.95) -> None:
        """Decay relevance score over time."""
        self.relevance_score *= decay_factor
        self.updated_at = datetime.now()

    def refresh_access(self) -> None:
        """Refresh access time and increment counter."""
        self.access_count += 1
        self.updated_at = datetime.now()


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        pass


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 384):
        """Initialize mock provider."""
        self.dimension = dimension

    def embed(self, text: str) -> List[float]:
        """Generate mock embedding."""
        import hashlib

        # Deterministic but pseudo-random embedding
        seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        rng = [seed]

        def next_random():
            rng[0] = (rng[0] * 1103515245 + 12345) & 0x7FFFFFFF
            return (rng[0] / 0x7FFFFFFF) - 0.5

        return [next_random() for _ in range(self.dimension)]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate mock embeddings for batch."""
        return [self.embed(text) for text in texts]

    def get_dimension(self) -> int:
        """Get embedding dimension."""
        return self.dimension


@dataclass
class SemanticSearch:
    """Results from semantic search."""

    query: str
    query_embedding: List[float]
    results: List[Tuple[MemoryItem, float]]  # (item, similarity_score)
    threshold: float = 0.5

    def get_matches(self) -> List[MemoryItem]:
        """Get items above threshold."""
        return [item for item, score in self.results if score >= self.threshold]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "threshold": self.threshold,
            "results": [
                {
                    "item_id": item.item_id,
                    "content": item.content,
                    "similarity": score,
                    "memory_type": item.memory_type.value,
                }
                for item, score in self.results
            ],
        }


class SemanticMemory:
    """
    Semantic memory system with vector embeddings.

    Manages long-term memory with semantic similarity search,
    automatic consolidation, and configurable retention policies.
    """

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        retention_policy: RetentionPolicy = RetentionPolicy.ADAPTIVE,
        max_size: int = 10000,
        similarity_threshold: float = 0.5,
    ):
        """
        Initialize semantic memory.

        Args:
            embedding_provider: Provider for generating embeddings
            retention_policy: How to manage memory size
            max_size: Maximum number of memories to keep
            similarity_threshold: Minimum similarity for search results
        """
        self.embedding_provider = embedding_provider or MockEmbeddingProvider()
        self.retention_policy = retention_policy
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold

        self.memories: Dict[str, MemoryItem] = {}
        self.created_at = datetime.now()
        self.consolidation_count = 0

    def add_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        tags: Optional[List[str]] = None,
    ) -> MemoryItem:
        """
        Add a new memory with semantic embedding.

        Args:
            content: Memory content text
            memory_type: Type of memory
            tags: Optional metadata tags

        Returns:
            The added MemoryItem
        """
        # Generate embedding
        embedding = self.embedding_provider.embed(content)

        # Create memory item
        item = MemoryItem(
            content=content,
            embedding=embedding,
            memory_type=memory_type,
            tags=tags or [],
        )

        # Store memory
        self.memories[item.item_id] = item
        logger.info(f"Added memory: {item.item_id}")

        # Check retention policy
        self._apply_retention_policy()

        return item

    def search(
        self, query: str, top_k: int = 5, min_similarity: float = 0.0
    ) -> SemanticSearch:
        """
        Search for similar memories using semantic similarity.

        Args:
            query: Search query text
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold

        Returns:
            SemanticSearch results object
        """
        # Generate query embedding
        query_embedding = self.embedding_provider.embed(query)

        # Calculate similarities
        similarities = []
        for item_id, item in self.memories.items():
            similarity = self._cosine_similarity(query_embedding, item.embedding)
            if similarity >= min_similarity:
                similarities.append((item, similarity))

        # Sort by similarity and limit
        similarities.sort(key=lambda x: x[1], reverse=True)
        results = similarities[:top_k]

        # Update access counts
        for item, _ in results:
            item.refresh_access()

        return SemanticSearch(
            query=query,
            query_embedding=query_embedding,
            results=results,
            threshold=self.similarity_threshold,
        )

    def search_by_tag(
        self, tag: str, memory_type: Optional[MemoryType] = None
    ) -> List[MemoryItem]:
        """
        Find memories by tag.

        Args:
            tag: Tag to search for
            memory_type: Optional filter by memory type

        Returns:
            List of matching memories
        """
        results = [
            item
            for item in self.memories.values()
            if tag in item.tags
            and (memory_type is None or item.memory_type == memory_type)
        ]
        return sorted(results, key=lambda x: x.access_count, reverse=True)

    def consolidate_memory(self, similarity_threshold: float = 0.85) -> Dict[str, Any]:
        """
        Consolidate similar memories by creating summaries.

        Args:
            similarity_threshold: Similarity for considering memories similar

        Returns:
            Consolidation statistics
        """
        consolidated_count = 0
        merged_groups = 0
        original_count = len(self.memories)

        # Find similar memory clusters
        processed = set()
        for item_id, item in list(self.memories.items()):
            if item_id in processed:
                continue

            # Find similar items
            similar_items = [item]
            for other_id, other_item in self.memories.items():
                if other_id != item_id and other_id not in processed:
                    similarity = self._cosine_similarity(
                        item.embedding, other_item.embedding
                    )
                    if similarity > similarity_threshold:
                        similar_items.append(other_item)
                        processed.add(other_id)

            # Consolidate if multiple similar items found
            if len(similar_items) > 1:
                # Create summary
                summary = self._create_summary(similar_items)
                item.summary = summary
                item.related_items = [i.item_id for i in similar_items[1:]]

                # Remove redundant items
                for other_item in similar_items[1:]:
                    del self.memories[other_item.item_id]
                    consolidated_count += 1

                merged_groups += 1
                processed.add(item_id)

        self.consolidation_count += 1
        stats = {
            "original_count": original_count,
            "final_count": len(self.memories),
            "consolidated_count": consolidated_count,
            "merged_groups": merged_groups,
            "consolidation_number": self.consolidation_count,
        }
        logger.info(f"Memory consolidation: {stats}")
        return stats

    def decay_all_relevance(self, decay_factor: float = 0.98) -> None:
        """
        Apply relevance decay to all memories.

        Args:
            decay_factor: Multiplication factor (0-1)
        """
        for item in self.memories.values():
            item.decay_relevance(decay_factor)

    def get_statistics(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        if not self.memories:
            return {
                "total_memories": 0,
                "memory_types": {},
                "avg_age": None,
                "avg_access_count": 0,
                "total_size_bytes": 0,
            }

        memory_types = {}
        total_accesses = 0
        total_age = 0

        for item in self.memories.values():
            memory_types[item.memory_type.value] = (
                memory_types.get(item.memory_type.value, 0) + 1
            )
            total_accesses += item.access_count
            age = (datetime.now() - item.created_at).total_seconds()
            total_age += age

        avg_age = total_age / len(self.memories) if self.memories else 0
        avg_access = total_accesses / len(self.memories) if self.memories else 0

        # Estimate size
        size_bytes = sum(len(item.to_dict().__str__().encode()) for item in self.memories.values())

        return {
            "total_memories": len(self.memories),
            "memory_types": memory_types,
            "avg_age_seconds": avg_age,
            "avg_access_count": avg_access,
            "total_size_bytes": size_bytes,
            "embedding_dimension": self.embedding_provider.get_dimension(),
            "retention_policy": self.retention_policy.value,
        }

    def to_json(self) -> str:
        """Export memory to JSON."""
        memories_data = [item.to_dict() for item in self.memories.values()]
        return json.dumps(
            {
                "created_at": self.created_at.isoformat(),
                "stats": self.get_statistics(),
                "memories": memories_data,
            },
            indent=2,
        )

    def _cosine_similarity(
        self, vec1: List[float], vec2: List[float]
    ) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _apply_retention_policy(self) -> None:
        """Apply retention policy to manage memory size."""
        if len(self.memories) <= self.max_size:
            return

        if self.retention_policy == RetentionPolicy.INDEFINITE:
            return
        elif self.retention_policy == RetentionPolicy.SIZE_LIMITED:
            # Remove least relevant items
            items = sorted(
                self.memories.values(),
                key=lambda x: (x.relevance_score, x.access_count),
            )
            for item in items[: len(self.memories) - self.max_size]:
                del self.memories[item.item_id]
        elif self.retention_policy == RetentionPolicy.TIME_BASED:
            # Remove oldest items
            cutoff_age = timedelta(days=30)
            now = datetime.now()
            for item_id in list(self.memories.keys()):
                item = self.memories[item_id]
                if now - item.created_at > cutoff_age:
                    del self.memories[item_id]
        elif self.retention_policy == RetentionPolicy.ADAPTIVE:
            # Remove low-relevance, old, and infrequently accessed items
            items = sorted(
                self.memories.values(),
                key=lambda x: (
                    x.relevance_score * (x.access_count + 1),
                    (datetime.now() - x.created_at).total_seconds(),
                ),
            )
            for item in items[: max(1, len(self.memories) - self.max_size)]:
                del self.memories[item.item_id]

    @staticmethod
    def _create_summary(items: List[MemoryItem]) -> str:
        """Create a summary from multiple memory items."""
        # Simple concatenation with length limit
        contents = [item.content for item in items]
        summary = " | ".join(contents)
        if len(summary) > 500:
            summary = summary[:497] + "..."
        return summary


def create_semantic_memory(
    max_size: int = 1000,
    retention_policy: str = "adaptive",
) -> SemanticMemory:
    """
    Factory function to create semantic memory.

    Args:
        max_size: Maximum number of memories
        retention_policy: Policy name (indefinite, time_based, size_limited, adaptive)

    Returns:
        Configured SemanticMemory instance
    """
    policy = RetentionPolicy[retention_policy.upper()]
    return SemanticMemory(
        retention_policy=policy,
        max_size=max_size,
    )


__all__ = [
    "MemoryType",
    "MemoryItem",
    "EmbeddingModel",
    "RetentionPolicy",
    "EmbeddingProvider",
    "MockEmbeddingProvider",
    "SemanticSearch",
    "SemanticMemory",
    "create_semantic_memory",
]
