"""Tests for React Pattern Enhancement."""
import pytest
import asyncio
from agent_sdk.planning.react_enhanced import (
    Thought, Action, Observation, ReactCycle,
    ReasoningEngine, ActionSelector, ObservationProcessor,
    EnhancedReactAgent,
)


class TestThought:
    def test_create_thought(self):
        thought = Thought(
            content="Test thought",
            reasoning_type="analysis",
            confidence=0.8,
        )
        assert thought.content == "Test thought"
        assert thought.confidence == 0.8

    def test_thought_to_dict(self):
        thought = Thought("content", "planning", 0.7)
        d = thought.to_dict()
        assert d["content"] == "content"
        assert d["type"] == "planning"


class TestAction:
    def test_create_action(self):
        action = Action(
            tool_name="search",
            parameters={"query": "test"},
        )
        assert action.tool_name == "search"
        assert action.parameters["query"] == "test"

    def test_action_to_dict(self):
        action = Action("calc", {"expr": "1+1"})
        d = action.to_dict()
        assert d["tool"] == "calc"


class TestObservation:
    def test_create_observation(self):
        obs = Observation(
            action_id="act1",
            result="success",
            success=True,
        )
        assert obs.result == "success"
        assert obs.success is True

    def test_observation_to_dict(self):
        obs = Observation("act1", "result", True, None)
        d = obs.to_dict()
        assert d["success"] is True


class TestReactCycle:
    def test_create_cycle(self):
        cycle = ReactCycle(cycle_id="c1")
        assert cycle.cycle_id == "c1"
        assert not cycle.is_complete()

    def test_add_thought(self):
        cycle = ReactCycle("c1")
        thought = Thought("test", "analysis")
        cycle.add_thought(thought)
        assert len(cycle.thoughts) == 1

    def test_cycle_complete(self):
        cycle = ReactCycle("c1")
        cycle.set_observation(Observation("a1", "result", True))
        assert cycle.is_complete()


class TestReasoningEngine:
    @pytest.mark.asyncio
    async def test_reasoning_engine_creation(self):
        engine = ReasoningEngine()
        assert engine.context_size == 10

    @pytest.mark.asyncio
    async def test_reason(self):
        engine = ReasoningEngine()
        thoughts = await engine.reason("What is 2+2?")
        assert len(thoughts) >= 1
        assert any(t.reasoning_type == "analysis" for t in thoughts)


class TestActionSelector:
    def test_action_selector_creation(self):
        tools = {"search": lambda x: []}
        selector = ActionSelector(tools)
        assert "search" in selector.get_available_tools()

    @pytest.mark.asyncio
    async def test_select_action(self):
        tools = {"search": lambda x: []}
        selector = ActionSelector(tools)
        thought = Thought("search for test", "planning", 0.9)
        action = await selector.select_action([thought])
        assert action is not None
        assert action.tool_name == "search"


class TestObservationProcessor:
    def test_processor_creation(self):
        proc = ObservationProcessor()
        assert proc.success_count == 0

    @pytest.mark.asyncio
    async def test_process_success(self):
        proc = ObservationProcessor()
        action = Action("test", {})
        obs = await proc.process_observation(action, "result", None)
        assert obs.success is True
        assert proc.success_count == 1

    @pytest.mark.asyncio
    async def test_process_failure(self):
        proc = ObservationProcessor()
        action = Action("test", {})
        obs = await proc.process_observation(action, None, "error")
        assert obs.success is False
        assert proc.failure_count == 1


class TestEnhancedReactAgent:
    def test_agent_creation(self):
        tools = {"search": lambda x: []}
        agent = EnhancedReactAgent(tools, max_cycles=3)
        assert agent.max_cycles == 3

    @pytest.mark.asyncio
    async def test_agent_run(self):
        tools = {"search": lambda query: ["result1"]}
        agent = EnhancedReactAgent(tools, max_cycles=2)

        steps = []
        async for step_type, data in agent.run("test query"):
            steps.append(step_type)

        assert len(steps) > 0
        assert len(agent.get_cycles()) > 0

    def test_agent_summary(self):
        tools = {"search": lambda x: []}
        agent = EnhancedReactAgent(tools)
        summary = agent.get_summary()
        assert "total_cycles" in summary
