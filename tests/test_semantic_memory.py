"""
Tests for semantic memory implementation.
"""

import pytest
from datetime import datetime, timedelta
from agent_sdk.memory import (
    MemoryType,
    MemoryItem,
    RetentionPolicy,
    MockEmbeddingProvider,
    SemanticMemory,
    SemanticSearch,
    create_semantic_memory,
)


class TestMemoryItem:
    """Test MemoryItem functionality."""

    def test_create_memory_item(self):
        """Test creating a memory item."""
        embedding = [0.1, 0.2, 0.3]
        item = MemoryItem(
            content="Python is a programming language",
            embedding=embedding,
            memory_type=MemoryType.FACTUAL,
        )
        assert item.content == "Python is a programming language"
        assert item.embedding == embedding
        assert item.memory_type == MemoryType.FACTUAL
        assert item.item_id is not None

    def test_memory_item_with_tags(self):
        """Test memory item with tags."""
        item = MemoryItem(
            content="Test", embedding=[0.1], memory_type=MemoryType.SEMANTIC, tags=["python", "learning"]
        )
        assert "python" in item.tags
        assert "learning" in item.tags

    def test_refresh_access(self):
        """Test access counter and timestamp."""
        item = MemoryItem(content="Test", embedding=[0.1], memory_type=MemoryType.FACTUAL)
        initial_time = item.updated_at
        item.refresh_access()
        assert item.access_count == 1
        assert item.updated_at >= initial_time

    def test_decay_relevance(self):
        """Test relevance decay."""
        item = MemoryItem(content="Test", embedding=[0.1], memory_type=MemoryType.FACTUAL, relevance_score=1.0)
        item.decay_relevance(decay_factor=0.9)
        assert item.relevance_score == pytest.approx(0.9, rel=0.01)
        item.decay_relevance(decay_factor=0.9)
        assert item.relevance_score == pytest.approx(0.81, rel=0.01)

    def test_memory_item_to_dict(self):
        """Test converting memory item to dictionary."""
        item = MemoryItem(
            content="Test content",
            embedding=[0.1, 0.2],
            memory_type=MemoryType.PROCEDURAL,
            tags=["test"],
        )
        item_dict = item.to_dict()
        assert item_dict["content"] == "Test content"
        assert item_dict["memory_type"] == "procedural"
        assert "test" in item_dict["tags"]
        assert "created_at" in item_dict


class TestMockEmbeddingProvider:
    """Test mock embedding provider."""

    def test_mock_embedding_dimension(self):
        """Test embedding dimension."""
        provider = MockEmbeddingProvider(dimension=384)
        embedding = provider.embed("test")
        assert len(embedding) == 384

    def test_mock_embedding_deterministic(self):
        """Test that same text produces same embedding."""
        provider = MockEmbeddingProvider(dimension=128)
        emb1 = provider.embed("hello world")
        emb2 = provider.embed("hello world")
        assert emb1 == emb2

    def test_mock_embedding_different_text(self):
        """Test that different texts produce different embeddings."""
        provider = MockEmbeddingProvider(dimension=128)
        emb1 = provider.embed("hello")
        emb2 = provider.embed("world")
        assert emb1 != emb2

    def test_batch_embedding(self):
        """Test batch embedding."""
        provider = MockEmbeddingProvider(dimension=64)
        texts = ["text1", "text2", "text3"]
        embeddings = provider.embed_batch(texts)
        assert len(embeddings) == 3
        assert all(len(e) == 64 for e in embeddings)


class TestSemanticMemory:
    """Test semantic memory functionality."""

    def test_create_semantic_memory(self):
        """Test creating semantic memory."""
        memory = SemanticMemory()
        assert len(memory.memories) == 0
        assert memory.retention_policy == RetentionPolicy.ADAPTIVE

    def test_add_memory(self):
        """Test adding a memory."""
        memory = SemanticMemory()
        item = memory.add_memory("Python is great", memory_type=MemoryType.FACTUAL)
        assert item is not None
        assert item.item_id in memory.memories
        assert len(memory.memories) == 1

    def test_add_multiple_memories(self):
        """Test adding multiple memories."""
        memory = SemanticMemory()
        memory.add_memory("Memory 1", memory_type=MemoryType.FACTUAL)
        memory.add_memory("Memory 2", memory_type=MemoryType.PROCEDURAL)
        memory.add_memory("Memory 3", memory_type=MemoryType.EPISODIC)
        assert len(memory.memories) == 3

    def test_semantic_search(self):
        """Test semantic search."""
        memory = SemanticMemory()
        memory.add_memory("Python is a programming language", tags=["python"])
        memory.add_memory("JavaScript is also a language", tags=["javascript"])
        memory.add_memory("Dogs are animals", tags=["animals"])

        results = memory.search("programming languages", top_k=2)
        assert len(results.results) > 0
        # First result should be about programming
        assert results.results[0][0].content == "Python is a programming language"

    def test_search_by_tag(self):
        """Test searching by tag."""
        memory = SemanticMemory()
        memory.add_memory("Python basics", tags=["python", "tutorial"])
        memory.add_memory("Python advanced", tags=["python", "advanced"])
        memory.add_memory("JavaScript", tags=["javascript"])

        python_items = memory.search_by_tag("python")
        assert len(python_items) == 2
        javascript_items = memory.search_by_tag("javascript")
        assert len(javascript_items) == 1

    def test_search_by_memory_type(self):
        """Test filtering by memory type during search."""
        memory = SemanticMemory()
        memory.add_memory("Fact 1", memory_type=MemoryType.FACTUAL, tags=["test"])
        memory.add_memory("Fact 2", memory_type=MemoryType.FACTUAL, tags=["test"])
        memory.add_memory("Procedure 1", memory_type=MemoryType.PROCEDURAL, tags=["test"])

        factual_items = memory.search_by_tag("test", memory_type=MemoryType.FACTUAL)
        assert len(factual_items) == 2

    def test_consolidate_memory(self):
        """Test memory consolidation."""
        memory = SemanticMemory()
        # Add very similar memories
        memory.add_memory("Python is a language")
        memory.add_memory("Python is a language")  # Identical
        memory.add_memory("Different topic")

        original_count = len(memory.memories)
        stats = memory.consolidate_memory(similarity_threshold=0.95)
        # Should consolidate duplicate memories
        assert stats["consolidated_count"] > 0

    def test_decay_relevance(self):
        """Test decaying relevance across all memories."""
        memory = SemanticMemory()
        item1 = memory.add_memory("Memory 1")
        item2 = memory.add_memory("Memory 2")
        initial_score1 = item1.relevance_score
        initial_score2 = item2.relevance_score

        memory.decay_all_relevance(decay_factor=0.9)
        assert memory.memories[item1.item_id].relevance_score < initial_score1
        assert memory.memories[item2.item_id].relevance_score < initial_score2

    def test_get_statistics(self):
        """Test getting memory statistics."""
        memory = SemanticMemory()
        memory.add_memory("Fact 1", memory_type=MemoryType.FACTUAL)
        memory.add_memory("Procedure 1", memory_type=MemoryType.PROCEDURAL)
        memory.add_memory("Event 1", memory_type=MemoryType.EPISODIC)

        stats = memory.get_statistics()
        assert stats["total_memories"] == 3
        assert "memory_types" in stats
        assert stats["memory_types"]["factual"] == 1
        assert stats["memory_types"]["procedural"] == 1
        assert stats["memory_types"]["episodic"] == 1

    def test_retention_policy_size_limited(self):
        """Test size-limited retention policy."""
        memory = SemanticMemory(
            retention_policy=RetentionPolicy.SIZE_LIMITED, max_size=2
        )
        memory.add_memory("Memory 1", relevance_score=0.5)
        memory.add_memory("Memory 2", relevance_score=0.8)
        memory.add_memory("Memory 3", relevance_score=0.9)
        # Should keep only 2 memories
        assert len(memory.memories) <= 2

    def test_retention_policy_adaptive(self):
        """Test adaptive retention policy."""
        memory = SemanticMemory(
            retention_policy=RetentionPolicy.ADAPTIVE, max_size=2
        )
        item1 = memory.add_memory("Memory 1", relevance_score=0.3)
        item2 = memory.add_memory("Memory 2", relevance_score=0.9)
        item3 = memory.add_memory("Memory 3", relevance_score=0.95)

        # Access high-relevance memory to increase priority
        memory.search("Memory 2")

        assert len(memory.memories) <= 2
        # High-relevance items should be kept
        assert item3.item_id in memory.memories or item2.item_id in memory.memories

    def test_memory_to_json(self):
        """Test exporting memory to JSON."""
        memory = SemanticMemory()
        memory.add_memory("Memory 1", tags=["test"])
        memory.add_memory("Memory 2", tags=["test"])

        json_str = memory.to_json()
        assert "memories" in json_str
        assert '"total_memories": 2' in json_str or '"total_memories":2' in json_str


class TestSemanticSearch:
    """Test semantic search results."""

    def test_search_results(self):
        """Test semantic search result object."""
        embedding = [0.1, 0.2, 0.3]
        item1 = MemoryItem("Test 1", embedding, MemoryType.FACTUAL)
        item2 = MemoryItem("Test 2", embedding, MemoryType.FACTUAL)

        results = SemanticSearch(
            query="test",
            query_embedding=embedding,
            results=[(item1, 0.9), (item2, 0.7)],
            threshold=0.5,
        )

        matches = results.get_matches()
        assert len(matches) == 2

    def test_search_threshold_filtering(self):
        """Test threshold filtering in results."""
        embedding = [0.1, 0.2, 0.3]
        item1 = MemoryItem("Test 1", embedding, MemoryType.FACTUAL)
        item2 = MemoryItem("Test 2", embedding, MemoryType.FACTUAL)

        results = SemanticSearch(
            query="test",
            query_embedding=embedding,
            results=[(item1, 0.9), (item2, 0.4)],
            threshold=0.5,
        )

        matches = results.get_matches()
        assert len(matches) == 1
        assert matches[0].item_id == item1.item_id

    def test_search_to_dict(self):
        """Test converting search results to dict."""
        embedding = [0.1, 0.2]
        item = MemoryItem("Test", embedding, MemoryType.FACTUAL)
        results = SemanticSearch(
            query="test query",
            query_embedding=embedding,
            results=[(item, 0.85)],
            threshold=0.5,
        )

        result_dict = results.to_dict()
        assert result_dict["query"] == "test query"
        assert len(result_dict["results"]) == 1
        assert result_dict["results"][0]["similarity"] == 0.85


class TestCreateSemanticMemory:
    """Test factory function."""

    def test_create_with_defaults(self):
        """Test creating with default settings."""
        memory = create_semantic_memory()
        assert memory.max_size == 1000
        assert memory.retention_policy == RetentionPolicy.ADAPTIVE

    def test_create_with_custom_policy(self):
        """Test creating with custom retention policy."""
        memory = create_semantic_memory(retention_policy="size_limited")
        assert memory.retention_policy == RetentionPolicy.SIZE_LIMITED

    def test_create_with_custom_size(self):
        """Test creating with custom max size."""
        memory = create_semantic_memory(max_size=500)
        assert memory.max_size == 500


class TestSemanticMemoryIntegration:
    """Integration tests for semantic memory."""

    def test_complete_memory_workflow(self):
        """Test complete workflow: add, search, consolidate."""
        memory = create_semantic_memory(max_size=100)

        # Add various memories
        memory.add_memory(
            "Python is a high-level language",
            memory_type=MemoryType.FACTUAL,
            tags=["python", "programming"],
        )
        memory.add_memory(
            "Python supports OOP",
            memory_type=MemoryType.FACTUAL,
            tags=["python", "programming"],
        )
        memory.add_memory(
            "To use Python, install it first",
            memory_type=MemoryType.PROCEDURAL,
            tags=["python", "setup"],
        )

        # Search for information
        results = memory.search("Python programming", top_k=2)
        assert len(results.results) > 0

        # Get statistics
        stats = memory.get_statistics()
        assert stats["total_memories"] == 3

        # Consolidate similar memories
        consolidation = memory.consolidate_memory()
        assert "consolidated_count" in consolidation

    def test_memory_decay_over_time(self):
        """Test relevance decay over time."""
        memory = SemanticMemory()
        item = memory.add_memory("Important fact", relevance_score=1.0)
        initial_score = memory.memories[item.item_id].relevance_score

        # Simulate aging
        for _ in range(5):
            memory.decay_all_relevance(decay_factor=0.9)

        final_score = memory.memories[item.item_id].relevance_score
        assert final_score < initial_score

    def test_search_with_multiple_queries(self):
        """Test multiple sequential searches."""
        memory = SemanticMemory()
        memory.add_memory("Python tutorial", tags=["python"])
        memory.add_memory("JavaScript guide", tags=["javascript"])
        memory.add_memory("Ruby basics", tags=["ruby"])

        # First search
        results1 = memory.search("Python", top_k=1)
        assert results1.results[0][0].content == "Python tutorial"

        # Second search - different query
        results2 = memory.search("JavaScript", top_k=1)
        assert results2.results[0][0].content == "JavaScript guide"

        # Check access counts were updated
        python_memory = list(memory.memories.values())[0]
        javascript_memory = list(memory.memories.values())[1]
        assert python_memory.access_count >= 1
        assert javascript_memory.access_count >= 1
