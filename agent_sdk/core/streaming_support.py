"""
Streaming Support: Enable progressive output and streaming responses for agents.

Provides SSE (Server-Sent Events) endpoints, WebSocket support, and streaming
message handling for real-time agent output delivery.
"""

from typing import Any, AsyncIterator, Callable, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import asyncio
from datetime import datetime


class StreamEventType(str, Enum):
    """Types of streaming events."""
    START = "start"
    THINKING = "thinking"
    ACTION = "action"
    OBSERVATION = "observation"
    STEP = "step"
    TOKEN = "token"
    PROGRESS = "progress"
    ERROR = "error"
    END = "end"


@dataclass
class StreamingMessage:
    """Represents a single streaming message in the event stream."""
    event_type: StreamEventType
    content: str
    step_number: Optional[int] = None
    agent_id: Optional[str] = None
    tool_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_sse_format(self) -> str:
        """Convert message to SSE format."""
        data = {
            "event": self.event_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.step_number is not None:
            data["step"] = self.step_number
        if self.agent_id:
            data["agent_id"] = self.agent_id
        if self.tool_name:
            data["tool"] = self.tool_name
        if self.metadata:
            data["metadata"] = self.metadata

        return f"data: {json.dumps(data)}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class StreamingResponse:
    """Manages streaming responses and progressive output."""

    def __init__(
        self,
        stream_fn: AsyncIterator[StreamingMessage],
        media_type: str = "text/event-stream",
    ):
        """
        Initialize streaming response.

        Args:
            stream_fn: Async iterator yielding StreamingMessage objects
            media_type: MIME type for response
        """
        self.stream_fn = stream_fn
        self.media_type = media_type
        self.headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": media_type,
        }

    async def __aiter__(self) -> AsyncIterator[str]:
        """Iterate over streaming messages in SSE format."""
        async for message in self.stream_fn:
            yield message.to_sse_format()


class StreamBuffer:
    """Buffers streaming messages for ordered delivery."""

    def __init__(self, buffer_size: int = 100):
        """
        Initialize stream buffer.

        Args:
            buffer_size: Maximum buffer size
        """
        self.buffer_size = buffer_size
        self.buffer: List[StreamingMessage] = []
        self.lock = asyncio.Lock()

    async def add(self, message: StreamingMessage) -> None:
        """Add message to buffer."""
        async with self.lock:
            self.buffer.append(message)
            if len(self.buffer) > self.buffer_size:
                self.buffer.pop(0)

    async def get_all(self) -> List[StreamingMessage]:
        """Get all buffered messages."""
        async with self.lock:
            return self.buffer.copy()

    async def clear(self) -> None:
        """Clear the buffer."""
        async with self.lock:
            self.buffer.clear()

    async def flush_to_iter(
        self,
    ) -> AsyncIterator[StreamingMessage]:
        """Convert buffer to async iterator."""
        for message in await self.get_all():
            yield message


class StreamAggregator:
    """Aggregates multiple streams into a single stream."""

    def __init__(self):
        self.streams: Dict[str, AsyncIterator[StreamingMessage]] = {}

    def add_stream(
        self,
        stream_id: str,
        stream: AsyncIterator[StreamingMessage],
    ) -> None:
        """Add a stream to aggregate."""
        self.streams[stream_id] = stream

    async def aggregate(self) -> AsyncIterator[StreamingMessage]:
        """Aggregate all streams into a single iterator."""
        # Create tasks for all streams
        tasks = []
        for stream_id, stream in self.streams.items():
            tasks.append(self._consume_stream(stream_id, stream))

        # Process all streams concurrently
        async def process_streams():
            await asyncio.sleep(0)  # Yield control
            for coro in tasks:
                async for message in coro:
                    yield message

        async for message in process_streams():
            yield message

    async def _consume_stream(
        self,
        stream_id: str,
        stream: AsyncIterator[StreamingMessage],
    ) -> Optional[StreamingMessage]:
        """Consume messages from a single stream."""
        async for message in stream:
            message.agent_id = stream_id
            yield message


class TokenCounter:
    """Counts tokens streamed in real-time."""

    def __init__(self):
        self.token_count = 0
        self.character_count = 0

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation).

        Args:
            text: Text to count tokens from

        Returns:
            Estimated token count (1 token ~= 4 chars)
        """
        tokens = max(1, len(text) // 4)
        self.token_count += tokens
        self.character_count += len(text)
        return tokens

    def reset(self) -> None:
        """Reset counters."""
        self.token_count = 0
        self.character_count = 0

    def get_stats(self) -> Dict[str, int]:
        """Get token/character statistics."""
        return {
            "tokens": self.token_count,
            "characters": self.character_count,
        }


class ProgressTracker:
    """Tracks progress of streaming operations."""

    def __init__(self, total_steps: int):
        """
        Initialize progress tracker.

        Args:
            total_steps: Total steps expected
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.completed_steps: List[int] = []

    async def update(self, step: int) -> StreamingMessage:
        """
        Update progress.

        Args:
            step: Step number completed

        Returns:
            Progress streaming message
        """
        self.current_step = step
        self.completed_steps.append(step)

        percentage = int((len(self.completed_steps) / self.total_steps) * 100)

        return StreamingMessage(
            event_type=StreamEventType.PROGRESS,
            content=f"{percentage}% complete ({len(self.completed_steps)}/{self.total_steps} steps)",
            metadata={
                "percentage": percentage,
                "completed": len(self.completed_steps),
                "total": self.total_steps,
            },
        )

    def get_progress(self) -> Dict[str, Any]:
        """Get current progress state."""
        percentage = int((len(self.completed_steps) / self.total_steps) * 100)
        return {
            "current_step": self.current_step,
            "completed_steps": len(self.completed_steps),
            "total_steps": self.total_steps,
            "percentage": percentage,
        }


async def stream_with_prefix(
    stream: AsyncIterator[StreamingMessage],
    prefix_message: str,
) -> AsyncIterator[StreamingMessage]:
    """
    Add a prefix message to a stream.

    Args:
        stream: Original stream
        prefix_message: Message to prepend

    Yields:
        StreamingMessage objects with prefix first
    """
    yield StreamingMessage(
        event_type=StreamEventType.START,
        content=prefix_message,
    )
    async for message in stream:
        yield message


async def stream_with_error_handling(
    stream: AsyncIterator[StreamingMessage],
    error_handler: Optional[Callable[[Exception], StreamingMessage]] = None,
) -> AsyncIterator[StreamingMessage]:
    """
    Wrap a stream with error handling.

    Args:
        stream: Original stream
        error_handler: Function to handle exceptions

    Yields:
        StreamingMessage objects with error handling
    """
    try:
        async for message in stream:
            yield message
    except Exception as e:
        if error_handler:
            yield error_handler(e)
        else:
            yield StreamingMessage(
                event_type=StreamEventType.ERROR,
                content=f"Streaming error: {str(e)}",
                metadata={"error_type": type(e).__name__},
            )


async def stream_throttle(
    stream: AsyncIterator[StreamingMessage],
    delay_ms: float = 100,
) -> AsyncIterator[StreamingMessage]:
    """
    Throttle stream output with a delay between messages.

    Args:
        stream: Original stream
        delay_ms: Delay in milliseconds between messages

    Yields:
        StreamingMessage objects with throttling
    """
    delay_seconds = delay_ms / 1000.0
    async for message in stream:
        yield message
        await asyncio.sleep(delay_seconds)
