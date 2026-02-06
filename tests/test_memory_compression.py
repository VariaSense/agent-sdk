"""Tests for Memory Compression."""
import pytest
from agent_sdk.memory.compression import (
    Message, SummarizedMessage, CompressionStrategy,
    SummarizationEngine, ImportanceSamplingEngine,
    TokenBudgetEngine, ClusteringEngine,
    MemoryCompressionManager, CompactionPolicy,
)


@pytest.fixture
def sample_messages():
    msgs = []
    for i in range(10):
        msg = Message(
            content=f"Message {i}: " + "test content " * 10,
            role="user" if i % 2 == 0 else "assistant",
            message_id=f"msg_{i}",
            timestamp=float(i),
        )
        msgs.append(msg)
    return msgs


class TestMessage:
    def test_create_message(self):
        msg = Message(
            content="Hello",
            role="user",
        )
        assert msg.content == "Hello"
        assert msg.role == "user"

    def test_estimate_tokens(self):
        msg = Message("test message", "user")
        tokens = msg.estimate_tokens()
        assert tokens > 0


class TestSummarizedMessage:
    def test_create_summary(self):
        summary = SummarizedMessage(
            summary="This is a summary",
            original_messages=["msg1", "msg2"],
            message_count=2,
        )
        assert summary.message_count == 2
        assert len(summary.original_messages) == 2


class TestSummarizationEngine:
    def test_engine_creation(self):
        engine = SummarizationEngine(window_size=5)
        assert engine.window_size == 5

    @pytest.mark.asyncio
    async def test_compress(self, sample_messages):
        engine = SummarizationEngine(window_size=3)
        compressed = await engine.compress(sample_messages)
        assert len(compressed) <= len(sample_messages)


class TestImportanceSamplingEngine:
    def test_engine_creation(self):
        engine = ImportanceSamplingEngine(importance_threshold=0.6)
        assert engine.importance_threshold == 0.6

    @pytest.mark.asyncio
    async def test_compress(self, sample_messages):
        engine = ImportanceSamplingEngine()
        # Set importance scores
        for msg in sample_messages:
            msg.importance_score = 0.5
        compressed = await engine.compress(sample_messages)
        assert len(compressed) <= len(sample_messages)

    @pytest.mark.asyncio
    async def test_score_importance(self):
        engine = ImportanceSamplingEngine()
        msg = Message("Important: critical error", "user")
        score = await engine.score_importance(msg)
        assert score > 0.5  # Should be higher due to keywords


class TestTokenBudgetEngine:
    def test_engine_creation(self):
        engine = TokenBudgetEngine(token_budget=1000)
        assert engine.token_budget == 1000

    @pytest.mark.asyncio
    async def test_compress(self, sample_messages):
        engine = TokenBudgetEngine(token_budget=500)
        compressed = await engine.compress(sample_messages)
        assert len(compressed) <= len(sample_messages)


class TestClusteringEngine:
    def test_engine_creation(self):
        engine = ClusteringEngine(cluster_size=3)
        assert engine.cluster_size == 3

    @pytest.mark.asyncio
    async def test_compress(self, sample_messages):
        engine = ClusteringEngine(cluster_size=2)
        compressed = await engine.compress(sample_messages)
        # Result should be shorter than original
        assert len(compressed) <= len(sample_messages)


class TestMemoryCompressionManager:
    @pytest.mark.asyncio
    async def test_manager_creation(self):
        manager = MemoryCompressionManager()
        assert manager.strategy == CompressionStrategy.SUMMARIZATION

    @pytest.mark.asyncio
    async def test_add_message(self):
        manager = MemoryCompressionManager()
        msg = Message("Test", "user")
        await manager.add_message(msg)
        assert len(manager.messages) == 1

    @pytest.mark.asyncio
    async def test_compress_memory(self, sample_messages):
        manager = MemoryCompressionManager()
        for msg in sample_messages:
            await manager.add_message(msg)

        compressed = await manager.compress_memory()
        assert len(compressed) <= len(sample_messages)

    @pytest.mark.asyncio
    async def test_get_compressed_context(self, sample_messages):
        manager = MemoryCompressionManager()
        for msg in sample_messages:
            await manager.add_message(msg)

        context = await manager.get_compressed_context()
        assert isinstance(context, str)
        assert len(context) > 0

    @pytest.mark.asyncio
    async def test_stats(self, sample_messages):
        manager = MemoryCompressionManager()
        for msg in sample_messages:
            await manager.add_message(msg)

        stats = manager.get_compression_stats()
        assert "original_messages" in stats
        assert stats["original_messages"] == len(sample_messages)

    @pytest.mark.asyncio
    async def test_clear(self):
        manager = MemoryCompressionManager()
        await manager.add_message(Message("test", "user"))
        assert len(manager.messages) == 1

        await manager.clear()
        assert len(manager.messages) == 0

    @pytest.mark.asyncio
    async def test_auto_compact_with_summary_hook(self, sample_messages):
        summaries = []

        def hook(summary):
            summaries.append(summary)

        manager = MemoryCompressionManager(
            strategy=CompressionStrategy.SUMMARIZATION,
            summarization_window_size=2,
            policy=CompactionPolicy(max_messages=2),
            summary_hook=hook,
            auto_compact=True,
        )

        for msg in sample_messages[:3]:
            await manager.add_message(msg)

        assert len(manager.compressed_history) > 0
        assert len(summaries) == len(manager.compressed_history)

    @pytest.mark.asyncio
    async def test_compaction_policy_max_tokens(self):
        manager = MemoryCompressionManager(
            policy=CompactionPolicy(max_tokens=5),
        )
        await manager.add_message(Message("short", "user"))
        await manager.add_message(Message("this is a longer message", "user"))

        assert manager.should_compact() is True
