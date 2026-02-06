"""Streaming support for real-time agent execution with Server-Sent Events.

Features:
- Server-sent events (SSE) streaming
- Token-by-token streaming with cost tracking
- Real-time metrics collection during streaming
- Multiple output formats (SSE, JSON, JSONL)
- Buffer management for efficient streaming
- Error handling and stream recovery
"""

import asyncio
import json
from typing import AsyncGenerator, Any, Dict, Iterator, Optional, List, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from enum import Enum


class StreamEventType(str, Enum):
    """Types of events that can be streamed during agent execution."""
    
    AGENT_START = "agent_start"           # Agent execution started
    AGENT_PLAN = "agent_plan"             # Plan generated
    STEP_START = "step_start"             # Step execution started
    STEP_THINKING = "step_thinking"       # Agent is thinking
    TOOL_CALL = "tool_call"               # Tool is being called
    TOOL_RESULT = "tool_result"           # Tool returned result
    STEP_COMPLETE = "step_complete"       # Step completed
    AGENT_COMPLETE = "agent_complete"     # Agent execution completed
    ERROR = "error"                       # Error occurred
    DEBUG = "debug"                       # Debug information
    TOKEN = "token"                       # LLM token streamed


@dataclass
class StreamEvent:
    """A single streaming event."""
    
    type: StreamEventType
    timestamp: str
    data: Dict[str, Any]
    step_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "timestamp": self.timestamp,
            "step_id": self.step_id,
            "data": self.data,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    def to_sse_format(self) -> str:
        """Convert to Server-Sent Events format."""
        return f"data: {self.to_json()}\n\n"


class StreamEventCollector:
    """Collects events during agent execution."""
    
    def __init__(self, max_buffer_size: int = 1000):
        self.events: list[StreamEvent] = []
        self.max_buffer_size = max_buffer_size
    
    def add_event(
        self,
        event_type: StreamEventType,
        data: Dict[str, Any],
        step_id: Optional[str] = None
    ) -> StreamEvent:
        """Add an event to the collector."""
        event = StreamEvent(
            type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data,
            step_id=step_id,
        )
        
        self.events.append(event)
        
        # Keep buffer bounded
        if len(self.events) > self.max_buffer_size:
            self.events.pop(0)
        
        return event
    
    def add_agent_start(self, agent_id: str, goal: str) -> StreamEvent:
        """Add agent start event."""
        return self.add_event(
            StreamEventType.AGENT_START,
            {"agent_id": agent_id, "goal": goal}
        )
    
    def add_plan_event(self, plan: Any) -> StreamEvent:
        """Add plan generated event."""
        return self.add_event(
            StreamEventType.AGENT_PLAN,
            {"plan": str(plan)}
        )
    
    def add_step_start(self, step_id: str, action: str) -> StreamEvent:
        """Add step start event."""
        return self.add_event(
            StreamEventType.STEP_START,
            {"action": action},
            step_id=step_id
        )
    
    def add_thinking(self, step_id: str, thought: str) -> StreamEvent:
        """Add thinking event."""
        return self.add_event(
            StreamEventType.STEP_THINKING,
            {"thought": thought},
            step_id=step_id
        )
    
    def add_tool_call(self, step_id: str, tool_name: str, params: Dict[str, Any]) -> StreamEvent:
        """Add tool call event."""
        return self.add_event(
            StreamEventType.TOOL_CALL,
            {"tool_name": tool_name, "parameters": params},
            step_id=step_id
        )
    
    def add_tool_result(self, step_id: str, tool_name: str, result: Any) -> StreamEvent:
        """Add tool result event."""
        return self.add_event(
            StreamEventType.TOOL_RESULT,
            {"tool_name": tool_name, "result": str(result)},
            step_id=step_id
        )
    
    def add_step_complete(self, step_id: str, result: Any) -> StreamEvent:
        """Add step complete event."""
        return self.add_event(
            StreamEventType.STEP_COMPLETE,
            {"result": str(result)},
            step_id=step_id
        )
    
    def add_agent_complete(self, agent_id: str, final_result: Any) -> StreamEvent:
        """Add agent complete event."""
        return self.add_event(
            StreamEventType.AGENT_COMPLETE,
            {"agent_id": agent_id, "result": str(final_result)}
        )
    
    def add_error(self, error_msg: str, step_id: Optional[str] = None) -> StreamEvent:
        """Add error event."""
        return self.add_event(
            StreamEventType.ERROR,
            {"error": error_msg},
            step_id=step_id
        )
    
    def add_token(self, token: str, model: Optional[str] = None) -> StreamEvent:
        """Add token streamed event."""
        return self.add_event(
            StreamEventType.TOKEN,
            {"token": token, "model": model}
        )
    
    def add_debug(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> StreamEvent:
        """Add debug event."""
        data = {"message": message}
        if metadata:
            data.update(metadata)
        return self.add_event(StreamEventType.DEBUG, data)
    
    def get_events(self) -> list[StreamEvent]:
        """Get all collected events."""
        return self.events.copy()
    
    def clear(self) -> None:
        """Clear all events."""
        self.events.clear()


class StreamBuffer:
    """Buffer for streaming events with async support."""
    
    def __init__(self, max_size: int = 100):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.max_size = max_size
    
    async def add(self, event: StreamEvent) -> None:
        """Add an event to the stream."""
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            # Remove oldest if full
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(event)
            except asyncio.QueueEmpty:
                pass
    
    async def get(self) -> StreamEvent:
        """Get next event from stream."""
        return await self.queue.get()
    
    async def stream(self) -> AsyncGenerator[StreamEvent, None]:
        """Stream all events as they arrive."""
        while True:
            event = await self.get()
            if event is None:  # End marker
                break
            yield event
    
    async def close(self) -> None:
        """Close the stream (send end marker)."""
        await self.add(None)


class StreamFormatter:
    """Format events for different streaming protocols."""
    
    @staticmethod
    def to_sse(event: StreamEvent) -> str:
        """Format event as Server-Sent Event."""
        return event.to_sse_format()
    
    @staticmethod
    def to_json_lines(event: StreamEvent) -> str:
        """Format event as JSON Lines (newline-delimited JSON)."""
        return event.to_json() + "\n"
    
    @staticmethod
    def to_compact(event: StreamEvent) -> str:
        """Format as compact JSON on single line."""
        return event.to_json()
    
    @staticmethod
    def to_pretty_json(event: StreamEvent) -> str:
        """Format as pretty-printed JSON."""
        return json.dumps(event.to_dict(), indent=2)


class StreamingAgent:
    """Wrapper for agents that provides streaming support."""
    
    def __init__(self, agent: Any):
        self.agent = agent
        self.event_collector = StreamEventCollector()
        self.stream_buffer = None
    
    async def run_stream(
        self,
        goal: str,
        stream_format: str = "sse"
    ) -> AsyncGenerator[str, None]:
        """Run agent and stream events.
        
        Args:
            goal: The goal for the agent
            stream_format: Format for events - "sse", "json", "compact", or "pretty"
        
        Yields:
            Formatted event strings
        """
        self.event_collector.clear()
        self.stream_buffer = StreamBuffer()
        
        # Start agent execution in background
        execution_task = asyncio.create_task(self._execute_agent(goal))
        
        # Stream events as they arrive
        formatter = self._get_formatter(stream_format)
        
        try:
            async for event in self.stream_buffer.stream():
                if event is None:
                    break
                yield formatter(event)
        finally:
            await execution_task
    
    async def _execute_agent(self, goal: str) -> None:
        """Execute agent and emit events."""
        agent_id = getattr(self.agent, 'id', 'unknown')
        
        try:
            self.event_collector.add_agent_start(agent_id, goal)
            await self.stream_buffer.add(self.event_collector.events[-1])
            
            # Simulate agent execution with events
            # In real implementation, hook into agent execution steps
            result = await asyncio.sleep(0.1)  # Placeholder
            
            self.event_collector.add_agent_complete(agent_id, "Completed")
            await self.stream_buffer.add(self.event_collector.events[-1])
        
        except Exception as e:
            self.event_collector.add_error(str(e))
            await self.stream_buffer.add(self.event_collector.events[-1])
        
        finally:
            await self.stream_buffer.close()
    
    @staticmethod
    def _get_formatter(format_name: str):
        """Get formatter function by name."""
        formatters = {
            "sse": StreamFormatter.to_sse,
            "json": StreamFormatter.to_json_lines,
            "compact": StreamFormatter.to_compact,
            "pretty": StreamFormatter.to_pretty_json,
        }
        return formatters.get(format_name, StreamFormatter.to_sse)


__all__ = [
    "StreamEventType",
    "StreamEvent",
    "StreamEventCollector",
    "StreamBuffer",
    "StreamFormatter",
    "StreamingAgent",
    "TokenCounter",
    "StreamCostCalculator",
    "StreamChunk",
    "StreamSession",
    "TokenStreamGenerator",
]


# ============================================================================
# Token Streaming and Cost Tracking
# ============================================================================

class TokenCounter:
    """Counts tokens in streamed content."""
    
    CHARS_PER_TOKEN = 4.0  # Simple estimation
    
    @staticmethod
    def count_tokens(text: str) -> int:
        """Estimate token count from text."""
        return max(1, int(len(text) / TokenCounter.CHARS_PER_TOKEN))
    
    @staticmethod
    def count_tokens_batch(texts: List[str]) -> List[int]:
        """Count tokens for multiple texts."""
        return [TokenCounter.count_tokens(text) for text in texts]


class StreamCostCalculator:
    """Calculate costs for streamed tokens."""
    
    def __init__(self, model_pricing: Optional[Dict[str, Dict[str, float]]] = None):
        """Initialize calculator with pricing data."""
        self.model_pricing = model_pricing or {}
    
    def calculate_token_cost(
        self,
        model: str,
        tokens: int,
        is_input: bool = False
    ) -> float:
        """Calculate cost for tokens."""
        if model not in self.model_pricing:
            return 0.0
        
        pricing = self.model_pricing[model]
        price_key = "input" if is_input else "output"
        
        if price_key not in pricing:
            return 0.0
        
        # Price is per 1M tokens
        price_per_token = pricing[price_key] / 1_000_000
        return tokens * price_per_token
    
    def add_model_pricing(self, model: str, input_price: float, output_price: float) -> None:
        """Add or update model pricing."""
        self.model_pricing[model] = {
            "input": input_price,
            "output": output_price
        }


@dataclass
class StreamChunk:
    """A single chunk of streamed tokens."""
    content: str
    tokens: int = 0
    cost: float = 0.0
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content": self.content,
            "tokens": self.tokens,
            "cost": self.cost,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    def to_sse(self) -> str:
        """Convert to SSE format."""
        data = json.dumps(self.to_dict())
        return f"data: {data}\n\n"


@dataclass
class StreamSession:
    """Metadata for a streaming session."""
    session_id: str
    model: str
    agent_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    chunk_count: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now(timezone.utc)
    
    def mark_complete(self):
        """Mark session as complete."""
        self.end_time = datetime.now(timezone.utc)
    
    def mark_error(self, error: str):
        """Mark session with error."""
        self.error = error
        self.mark_complete()
    
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    def tokens_per_second(self) -> float:
        """Calculate tokens per second."""
        duration = self.duration_ms() / 1000
        if duration == 0:
            return 0.0
        return self.total_tokens / duration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "model": self.model,
            "agent_id": self.agent_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "chunk_count": self.chunk_count,
            "duration_ms": self.duration_ms(),
            "tokens_per_second": self.tokens_per_second(),
            "error": self.error,
            "metadata": self.metadata
        }


class TokenStreamGenerator:
    """Generator for token streaming with cost tracking."""
    
    def __init__(
        self,
        session_id: str,
        model: str,
        agent_id: Optional[str] = None,
        cost_calculator: Optional[StreamCostCalculator] = None,
        buffer_size: int = 100
    ):
        """Initialize token stream generator."""
        self.session = StreamSession(
            session_id=session_id,
            model=model,
            agent_id=agent_id
        )
        self.chunks: List[StreamChunk] = []
        self.max_buffer_size = buffer_size
        self.cost_calculator = cost_calculator or StreamCostCalculator()
    
    def stream_tokens(
        self,
        source: Iterator[str],
        output_format: str = "raw"
    ) -> Iterator[str]:
        """
        Stream tokens with cost tracking.
        
        Args:
            source: Iterator of text tokens/chunks
            output_format: Output format (raw, json, sse)
            
        Yields:
            Streamed output in specified format
        """
        try:
            for text in source:
                # Count tokens and calculate cost
                tokens = TokenCounter.count_tokens(text)
                cost = self.cost_calculator.calculate_token_cost(
                    self.session.model,
                    tokens,
                    is_input=False
                )
                
                # Create chunk
                chunk = StreamChunk(
                    content=text,
                    tokens=tokens,
                    cost=cost
                )
                
                # Update session
                self.session.total_tokens += tokens
                self.session.total_cost += cost
                self.session.chunk_count += 1
                
                # Buffer chunk
                self.chunks.append(chunk)
                if len(self.chunks) > self.max_buffer_size:
                    self.chunks.pop(0)
                
                # Yield in requested format
                if output_format == "raw":
                    yield text
                elif output_format == "json":
                    yield chunk.to_json()
                elif output_format == "sse":
                    yield chunk.to_sse()
            
            # Mark as complete
            self.session.mark_complete()
            
        except Exception as e:
            self.session.mark_error(str(e))
            raise
    
    async def stream_tokens_async(
        self,
        source: AsyncGenerator[str, None],
        output_format: str = "raw"
    ) -> AsyncGenerator[str, None]:
        """Stream tokens asynchronously."""
        try:
            async for text in source:
                # Count tokens and calculate cost
                tokens = TokenCounter.count_tokens(text)
                cost = self.cost_calculator.calculate_token_cost(
                    self.session.model,
                    tokens,
                    is_input=False
                )
                
                # Create chunk
                chunk = StreamChunk(
                    content=text,
                    tokens=tokens,
                    cost=cost
                )
                
                # Update session
                self.session.total_tokens += tokens
                self.session.total_cost += cost
                self.session.chunk_count += 1
                
                # Buffer chunk
                self.chunks.append(chunk)
                if len(self.chunks) > self.max_buffer_size:
                    self.chunks.pop(0)
                
                # Yield in requested format
                if output_format == "raw":
                    yield text
                elif output_format == "json":
                    yield chunk.to_json()
                elif output_format == "sse":
                    yield chunk.to_sse()
                
                # Allow other tasks to run
                await asyncio.sleep(0)
            
            # Mark as complete
            self.session.mark_complete()
            
        except Exception as e:
            self.session.mark_error(str(e))
            raise
    
    def get_session(self) -> StreamSession:
        """Get stream session."""
        return self.session
    
    def get_chunks(self) -> List[StreamChunk]:
        """Get buffered chunks."""
        return self.chunks.copy()
    
    def get_content(self) -> str:
        """Get concatenated content."""
        return "".join(chunk.content for chunk in self.chunks)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get session summary."""
        return self.session.to_dict()
