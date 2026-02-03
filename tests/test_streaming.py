"""Tests for streaming support."""

import pytest
import asyncio
from agent_sdk.core.streaming import (
    StreamEventType,
    StreamEvent,
    StreamEventCollector,
    StreamFormatter,
    TokenCounter,
    StreamCostCalculator,
    StreamChunk,
    StreamSession,
    TokenStreamGenerator,
)


def test_stream_event_creation():
    """Test creating a stream event."""
    event = StreamEvent(
        type=StreamEventType.AGENT_START,
        timestamp="2024-01-01T00:00:00",
        data={"agent_id": "test-agent", "goal": "Test goal"},
    )
    
    assert event.type == StreamEventType.AGENT_START
    assert event.data["agent_id"] == "test-agent"


def test_stream_event_to_dict():
    """Test converting event to dictionary."""
    event = StreamEvent(
        type=StreamEventType.AGENT_START,
        timestamp="2024-01-01T00:00:00",
        data={"test": "data"},
        step_id="step-1",
    )
    
    event_dict = event.to_dict()
    
    assert event_dict["type"] == "agent_start"
    assert event_dict["data"]["test"] == "data"
    assert event_dict["step_id"] == "step-1"


def test_stream_event_to_sse_format():
    """Test converting event to SSE format."""
    event = StreamEvent(
        type=StreamEventType.TOOL_CALL,
        timestamp="2024-01-01T00:00:00",
        data={"tool": "calculator"},
    )
    
    sse = event.to_sse_format()
    
    assert sse.startswith("data: ")
    assert "\n\n" in sse


def test_event_collector_add_events():
    """Test adding events to collector."""
    collector = StreamEventCollector()
    
    collector.add_agent_start("agent-1", "Test goal")
    collector.add_thinking("step-1", "Let me think...")
    collector.add_tool_call("step-1", "calculator", {"a": 1, "b": 2})
    collector.add_tool_result("step-1", "calculator", "Result: 3")
    
    assert len(collector.get_events()) == 4


def test_event_collector_max_buffer():
    """Test buffer size limit."""
    collector = StreamEventCollector(max_buffer_size=5)
    
    for i in range(10):
        collector.add_agent_start(f"agent-{i}", f"Goal {i}")
    
    # Should only keep last 5
    assert len(collector.get_events()) <= 5


def test_event_collector_clear():
    """Test clearing collector."""
    collector = StreamEventCollector()
    
    collector.add_agent_start("agent-1", "Goal")
    assert len(collector.get_events()) > 0
    
    collector.clear()
    assert len(collector.get_events()) == 0


def test_stream_formatter_sse():
    """Test SSE formatter."""
    event = StreamEvent(
        type=StreamEventType.AGENT_START,
        timestamp="2024-01-01T00:00:00",
        data={"test": "data"},
    )
    
    sse = StreamFormatter.to_sse(event)
    
    assert "data: " in sse
    assert '"type": "agent_start"' in sse


def test_stream_formatter_json_lines():
    """Test JSON Lines formatter."""
    event = StreamEvent(
        type=StreamEventType.AGENT_COMPLETE,
        timestamp="2024-01-01T00:00:00",
        data={"result": "done"},
    )
    
    json_lines = StreamFormatter.to_json_lines(event)
    
    assert json_lines.endswith("\n")
    assert '"type": "agent_complete"' in json_lines


def test_stream_formatter_compact():
    """Test compact JSON formatter."""
    event = StreamEvent(
        type=StreamEventType.ERROR,
        timestamp="2024-01-01T00:00:00",
        data={"error": "Test error"},
    )
    
    compact = StreamFormatter.to_compact(event)
    
    assert "\n" not in compact  # Single line
    assert '"error": "Test error"' in compact


def test_stream_formatter_pretty():
    """Test pretty JSON formatter."""
    event = StreamEvent(
        type=StreamEventType.AGENT_PLAN,
        timestamp="2024-01-01T00:00:00",
        data={"plan": "Test plan"},
    )
    
    pretty = StreamFormatter.to_pretty_json(event)
    
    assert "\n" in pretty  # Multi-line
    assert "  " in pretty  # Indented


def test_stream_event_types():
    """Test all event types are defined."""
    event_types = [
        StreamEventType.AGENT_START,
        StreamEventType.AGENT_PLAN,
        StreamEventType.STEP_START,
        StreamEventType.STEP_THINKING,
        StreamEventType.TOOL_CALL,
        StreamEventType.TOOL_RESULT,
        StreamEventType.STEP_COMPLETE,
        StreamEventType.AGENT_COMPLETE,
        StreamEventType.ERROR,
        StreamEventType.DEBUG,
        StreamEventType.TOKEN,
    ]
    
    assert len(event_types) == 11
    for et in event_types:
        assert isinstance(et, StreamEventType)


def test_event_collector_step_id():
    """Test events with step IDs."""
    collector = StreamEventCollector()
    
    event1 = collector.add_step_start("step-1", "Action 1")
    event2 = collector.add_step_start("step-2", "Action 2")
    
    assert event1.step_id == "step-1"
    assert event2.step_id == "step-2"


def test_event_collector_events_sequence():
    """Test a complete event sequence."""
    collector = StreamEventCollector()
    
    # Agent execution flow
    collector.add_agent_start("agent-1", "Calculate 2 + 2")
    collector.add_plan_event("Use calculator tool")
    collector.add_step_start("step-1", "Call calculator")
    collector.add_thinking("step-1", "Need to add 2 + 2")
    collector.add_tool_call("step-1", "add", {"a": 2, "b": 2})
    collector.add_tool_result("step-1", "add", 4)
    collector.add_step_complete("step-1", "Successfully calculated")
    collector.add_agent_complete("agent-1", "Result is 4")
    
    events = collector.get_events()
    
    assert len(events) == 8
    assert events[0].type == StreamEventType.AGENT_START
    assert events[-1].type == StreamEventType.AGENT_COMPLETE


# ============================================================================
# Token Streaming Tests
# ============================================================================

class TestTokenCounter:
    """Test TokenCounter class."""
    
    def test_count_single_token(self):
        """Test counting a single token."""
        count = TokenCounter.count_tokens("hello")
        assert count >= 1
    
    def test_count_empty_string(self):
        """Test counting empty string."""
        count = TokenCounter.count_tokens("")
        assert count >= 1  # Minimum 1
    
    def test_count_long_text(self):
        """Test counting long text."""
        text = "a" * 1000
        count = TokenCounter.count_tokens(text)
        assert count > 100
    
    def test_count_batch(self):
        """Test counting multiple tokens."""
        texts = ["hello", "world", "test"]
        counts = TokenCounter.count_tokens_batch(texts)
        
        assert len(counts) == 3
        assert all(c >= 1 for c in counts)


class TestStreamCostCalculator:
    """Test StreamCostCalculator class."""
    
    def test_calculate_cost_known_model(self):
        """Test cost calculation for known model."""
        calc = StreamCostCalculator({
            "gpt-4": {"input": 0.03, "output": 0.06}
        })
        
        cost = calc.calculate_token_cost("gpt-4", 1000, is_input=False)
        assert cost > 0
    
    def test_calculate_cost_unknown_model(self):
        """Test cost calculation for unknown model."""
        calc = StreamCostCalculator()
        cost = calc.calculate_token_cost("unknown", 1000, is_input=False)
        
        assert cost == 0.0
    
    def test_input_vs_output_pricing(self):
        """Test different pricing for input vs output."""
        calc = StreamCostCalculator({
            "gpt-4": {"input": 0.03, "output": 0.06}
        })
        
        input_cost = calc.calculate_token_cost("gpt-4", 1000, is_input=True)
        output_cost = calc.calculate_token_cost("gpt-4", 1000, is_input=False)
        
        assert input_cost < output_cost
    
    def test_add_model_pricing(self):
        """Test adding new model pricing."""
        calc = StreamCostCalculator()
        calc.add_model_pricing("custom-model", 0.01, 0.02)
        
        cost = calc.calculate_token_cost("custom-model", 1000, is_input=False)
        assert cost > 0


class TestStreamChunk:
    """Test StreamChunk class."""
    
    def test_create_chunk(self):
        """Test creating a chunk."""
        chunk = StreamChunk(content="hello", tokens=2, cost=0.001)
        
        assert chunk.content == "hello"
        assert chunk.tokens == 2
        assert chunk.cost == 0.001
    
    def test_chunk_timestamp(self):
        """Test chunk has timestamp."""
        chunk = StreamChunk(content="test")
        assert chunk.timestamp is not None
    
    def test_chunk_to_dict(self):
        """Test chunk conversion to dict."""
        chunk = StreamChunk(content="hello", tokens=2, cost=0.001)
        data = chunk.to_dict()
        
        assert data["content"] == "hello"
        assert data["tokens"] == 2
        assert "timestamp" in data
    
    def test_chunk_to_sse(self):
        """Test chunk conversion to SSE format."""
        chunk = StreamChunk(content="hello", tokens=2)
        sse = chunk.to_sse()
        
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")


class TestStreamSession:
    """Test StreamSession class."""
    
    def test_create_session(self):
        """Test creating a session."""
        session = StreamSession(session_id="test_001", model="gpt-4")
        
        assert session.session_id == "test_001"
        assert session.model == "gpt-4"
        assert session.start_time is not None
    
    def test_session_mark_complete(self):
        """Test marking session complete."""
        session = StreamSession(session_id="test", model="gpt-4")
        
        assert session.end_time is None
        session.mark_complete()
        assert session.end_time is not None
    
    def test_session_mark_error(self):
        """Test marking session with error."""
        session = StreamSession(session_id="test", model="gpt-4")
        
        session.mark_error("Test error")
        
        assert session.error == "Test error"
        assert session.end_time is not None
    
    def test_session_to_dict(self):
        """Test session conversion to dict."""
        session = StreamSession(
            session_id="test",
            model="gpt-4",
            total_tokens=100,
            total_cost=0.006
        )
        session.mark_complete()
        
        data = session.to_dict()
        
        assert data["session_id"] == "test"
        assert data["model"] == "gpt-4"
        assert data["total_tokens"] == 100


class TestTokenStreamGenerator:
    """Test TokenStreamGenerator class."""
    
    def test_create_generator(self):
        """Test creating a generator."""
        gen = TokenStreamGenerator(
            session_id="test_001",
            model="gpt-4"
        )
        
        assert gen.session.session_id == "test_001"
        assert gen.session.model == "gpt-4"
    
    def test_stream_tokens_raw_format(self):
        """Test streaming in raw format."""
        gen = TokenStreamGenerator(session_id="test", model="gpt-4")
        tokens = ["hello", " ", "world"]
        
        chunks = list(gen.stream_tokens(iter(tokens), output_format="raw"))
        
        assert len(chunks) == len(tokens)
        assert chunks == tokens
    
    def test_stream_tokens_json_format(self):
        """Test streaming in JSON format."""
        gen = TokenStreamGenerator(session_id="test", model="gpt-4")
        tokens = ["hello"]
        
        chunks = list(gen.stream_tokens(iter(tokens), output_format="json"))
        
        assert len(chunks) > 0
        assert isinstance(chunks[0], str)
    
    def test_stream_tokens_sse_format(self):
        """Test streaming in SSE format."""
        gen = TokenStreamGenerator(session_id="test", model="gpt-4")
        tokens = ["hello"]
        
        chunks = list(gen.stream_tokens(iter(tokens), output_format="sse"))
        
        assert chunks[0].startswith("data: ")
        assert chunks[0].endswith("\n\n")
    
    def test_stream_updates_session(self):
        """Test that streaming updates session."""
        gen = TokenStreamGenerator(session_id="test", model="gpt-4")
        tokens = ["hello", " ", "world"]
        
        list(gen.stream_tokens(iter(tokens)))
        
        session = gen.get_session()
        
        assert session.total_tokens > 0
        assert session.chunk_count == len(tokens)
        assert session.end_time is not None
    
    def test_stream_calculates_cost(self):
        """Test that streaming calculates cost."""
        calc = StreamCostCalculator({
            "gpt-4": {"input": 0.03, "output": 0.06}
        })
        gen = TokenStreamGenerator(
            session_id="test",
            model="gpt-4",
            cost_calculator=calc
        )
        
        tokens = ["hello", "world"]
        list(gen.stream_tokens(iter(tokens)))
        
        assert gen.session.total_cost > 0
    
    def test_stream_buffers_chunks(self):
        """Test that chunks are buffered."""
        gen = TokenStreamGenerator(session_id="test", model="gpt-4")
        tokens = ["hello", " ", "world"]
        
        list(gen.stream_tokens(iter(tokens)))
        
        chunks = gen.get_chunks()
        
        assert len(chunks) > 0
        assert all(isinstance(c, StreamChunk) for c in chunks)
    
    def test_stream_get_content(self):
        """Test getting concatenated content."""
        gen = TokenStreamGenerator(session_id="test", model="gpt-4")
        tokens = ["hello", " ", "world"]
        
        list(gen.stream_tokens(iter(tokens)))
        
        content = gen.get_content()
        
        assert len(content) > 0
    
    def test_stream_error_handling(self):
        """Test error handling during streaming."""
        gen = TokenStreamGenerator(session_id="test", model="gpt-4")
        
        def error_source():
            yield "hello"
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            list(gen.stream_tokens(error_source()))
        
        assert gen.session.error is not None
    
    def test_stream_get_summary(self):
        """Test getting session summary."""
        gen = TokenStreamGenerator(session_id="test", model="gpt-4")
        tokens = ["hello", " ", "world"]
        
        list(gen.stream_tokens(iter(tokens)))
        
        summary = gen.get_summary()
        
        assert "session_id" in summary
        assert "total_tokens" in summary
        assert "total_cost" in summary


@pytest.mark.asyncio
async def test_async_stream_tokens():
    """Test asynchronous token streaming."""
    async def token_source():
        for token in ["hello", " ", "world"]:
            yield token
            await asyncio.sleep(0.001)
    
    gen = TokenStreamGenerator(session_id="async_test", model="gpt-4")
    
    chunks = []
    async for chunk in gen.stream_tokens_async(token_source()):
        chunks.append(chunk)
    
    assert len(chunks) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
