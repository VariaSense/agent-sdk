"""Tests for streaming support."""

import pytest
import asyncio
from agent_sdk.core.streaming import (
    StreamEventType,
    StreamEvent,
    StreamEventCollector,
    StreamFormatter,
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
