"""
Tests for Streaming Support.
"""

import pytest
import asyncio
from agent_sdk.core.streaming_support import (
    StreamingMessage,
    StreamingResponse,
    StreamBuffer,
    StreamAggregator,
    TokenCounter,
    ProgressTracker,
    stream_with_prefix,
    stream_with_error_handling,
    stream_throttle,
    StreamEventType,
)


@pytest.fixture
async def sample_stream():
    """Create a sample async stream."""
    async def stream_gen():
        for i in range(3):
            yield StreamingMessage(
                event_type=StreamEventType.TOKEN,
                content=f"token_{i}",
            )
    return stream_gen()


class TestStreamingMessage:
    """Test StreamingMessage class."""

    def test_create_message(self):
        """Test creating a message."""
        msg = StreamingMessage(
            event_type=StreamEventType.TOKEN,
            content="hello",
        )
        assert msg.content == "hello"
        assert msg.event_type == StreamEventType.TOKEN

    def test_message_with_metadata(self):
        """Test message with metadata."""
        msg = StreamingMessage(
            event_type=StreamEventType.ACTION,
            content="action",
            tool_name="search",
            metadata={"key": "value"},
        )
        assert msg.tool_name == "search"
        assert msg.metadata["key"] == "value"

    def test_to_sse_format(self):
        """Test SSE format conversion."""
        msg = StreamingMessage(
            event_type=StreamEventType.START,
            content="starting",
        )
        sse = msg.to_sse_format()

        assert "data:" in sse
        assert "starting" in sse
        assert "start" in sse

    def test_to_dict(self):
        """Test dict conversion."""
        msg = StreamingMessage(
            event_type=StreamEventType.END,
            content="finished",
        )
        d = msg.to_dict()

        assert d["content"] == "finished"
        assert d["event_type"] == "end"

    def test_to_json(self):
        """Test JSON conversion."""
        msg = StreamingMessage(
            event_type=StreamEventType.ERROR,
            content="error occurred",
        )
        json_str = msg.to_json()

        assert isinstance(json_str, str)
        assert "error occurred" in json_str


class TestStreamingResponse:
    """Test StreamingResponse class."""

    @pytest.mark.asyncio
    async def test_streaming_response(self):
        """Test streaming response."""
        async def gen():
            yield StreamingMessage(StreamEventType.TOKEN, "test")

        response = StreamingResponse(gen())
        assert response.media_type == "text/event-stream"

    @pytest.mark.asyncio
    async def test_streaming_response_iteration(self):
        """Test iterating over streaming response."""
        async def gen():
            yield StreamingMessage(StreamEventType.TOKEN, "a")
            yield StreamingMessage(StreamEventType.TOKEN, "b")

        response = StreamingResponse(gen())
        messages = []
        async for msg in response:
            messages.append(msg)

        assert len(messages) == 2
        assert "a" in messages[0]
        assert "b" in messages[1]


class TestStreamBuffer:
    """Test StreamBuffer class."""

    @pytest.mark.asyncio
    async def test_add_message(self):
        """Test adding message to buffer."""
        buffer = StreamBuffer()
        msg = StreamingMessage(StreamEventType.TOKEN, "test")

        await buffer.add(msg)
        all_msgs = await buffer.get_all()

        assert len(all_msgs) == 1
        assert all_msgs[0].content == "test"

    @pytest.mark.asyncio
    async def test_buffer_size_limit(self):
        """Test buffer size limit."""
        buffer = StreamBuffer(buffer_size=3)

        for i in range(5):
            msg = StreamingMessage(StreamEventType.TOKEN, f"msg_{i}")
            await buffer.add(msg)

        all_msgs = await buffer.get_all()
        assert len(all_msgs) <= 3

    @pytest.mark.asyncio
    async def test_clear_buffer(self):
        """Test clearing buffer."""
        buffer = StreamBuffer()
        msg = StreamingMessage(StreamEventType.TOKEN, "test")

        await buffer.add(msg)
        assert len(await buffer.get_all()) == 1

        await buffer.clear()
        assert len(await buffer.get_all()) == 0

    @pytest.mark.asyncio
    async def test_buffer_to_iter(self):
        """Test converting buffer to iterator."""
        buffer = StreamBuffer()

        for i in range(3):
            await buffer.add(StreamingMessage(StreamEventType.TOKEN, f"msg_{i}"))

        count = 0
        async for msg in buffer.flush_to_iter():
            count += 1

        assert count == 3


class TestTokenCounter:
    """Test TokenCounter class."""

    def test_count_tokens(self):
        """Test token counting."""
        counter = TokenCounter()
        count = counter.count_tokens("hello world test")

        assert count >= 1
        assert counter.token_count >= 1

    def test_multiple_counts(self):
        """Test counting multiple texts."""
        counter = TokenCounter()

        counter.count_tokens("hello")
        counter.count_tokens("world")

        assert counter.token_count > 0
        assert counter.character_count > 0

    def test_get_stats(self):
        """Test getting stats."""
        counter = TokenCounter()
        counter.count_tokens("test message")

        stats = counter.get_stats()
        assert "tokens" in stats
        assert "characters" in stats
        assert stats["tokens"] > 0

    def test_reset(self):
        """Test resetting counters."""
        counter = TokenCounter()
        counter.count_tokens("test")

        assert counter.token_count > 0

        counter.reset()
        assert counter.token_count == 0
        assert counter.character_count == 0


class TestProgressTracker:
    """Test ProgressTracker class."""

    @pytest.mark.asyncio
    async def test_update_progress(self):
        """Test updating progress."""
        tracker = ProgressTracker(total_steps=10)
        msg = await tracker.update(1)

        assert msg.event_type == StreamEventType.PROGRESS
        assert "complete" in msg.content

    @pytest.mark.asyncio
    async def test_progress_percentage(self):
        """Test progress percentage calculation."""
        tracker = ProgressTracker(total_steps=4)

        await tracker.update(1)
        await tracker.update(2)

        progress = tracker.get_progress()
        assert progress["percentage"] == 50

    @pytest.mark.asyncio
    async def test_get_progress_state(self):
        """Test getting progress state."""
        tracker = ProgressTracker(total_steps=5)

        await tracker.update(1)
        await tracker.update(2)

        progress = tracker.get_progress()
        assert progress["completed_steps"] == 2
        assert progress["total_steps"] == 5


class TestStreamHelpers:
    """Test stream helper functions."""

    @pytest.mark.asyncio
    async def test_stream_with_prefix(self):
        """Test adding prefix to stream."""
        async def gen():
            yield StreamingMessage(StreamEventType.TOKEN, "content")

        prefixed = stream_with_prefix(gen(), "Starting...")
        messages = []
        async for msg in prefixed:
            messages.append(msg)

        assert len(messages) == 2
        assert messages[0].event_type == StreamEventType.START
        assert "Starting" in messages[0].content

    @pytest.mark.asyncio
    async def test_stream_with_error_handling(self):
        """Test error handling in stream."""
        async def failing_gen():
            yield StreamingMessage(StreamEventType.TOKEN, "ok")
            raise ValueError("Stream error")

        wrapped = stream_with_error_handling(failing_gen())
        messages = []
        async for msg in wrapped:
            messages.append(msg)

        assert len(messages) == 2
        assert messages[1].event_type == StreamEventType.ERROR

    @pytest.mark.asyncio
    async def test_stream_throttle(self):
        """Test stream throttling."""
        async def gen():
            yield StreamingMessage(StreamEventType.TOKEN, "a")
            yield StreamingMessage(StreamEventType.TOKEN, "b")

        import time
        start = time.time()

        throttled = stream_throttle(gen(), delay_ms=50)
        count = 0
        async for msg in throttled:
            count += 1

        elapsed = time.time() - start
        assert count == 2
        assert elapsed >= 0.05  # At least one throttle delay


class TestStreamAggregator:
    """Test StreamAggregator class."""

    def test_create_aggregator(self):
        """Test creating aggregator."""
        agg = StreamAggregator()
        assert len(agg.streams) == 0

    @pytest.mark.asyncio
    async def test_add_stream(self):
        """Test adding stream."""
        agg = StreamAggregator()

        async def gen():
            yield StreamingMessage(StreamEventType.TOKEN, "test")

        agg.add_stream("stream1", gen())
        assert "stream1" in agg.streams

    @pytest.mark.asyncio
    async def test_aggregate_streams(self):
        """Test aggregating multiple streams."""
        agg = StreamAggregator()

        async def gen1():
            yield StreamingMessage(StreamEventType.TOKEN, "a")

        async def gen2():
            yield StreamingMessage(StreamEventType.TOKEN, "b")

        agg.add_stream("s1", gen1())
        agg.add_stream("s2", gen2())

        count = 0
        async for msg in agg.aggregate():
            count += 1

        assert count == 2
