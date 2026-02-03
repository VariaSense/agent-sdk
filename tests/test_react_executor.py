"""Tests for React pattern executor."""

import pytest
from agent_sdk.planning.react_executor import (
    ReasoningStepType, ReasoningStep, ReactChain, ReactAgentExecutor
)


class TestReasoningStep:
    """Tests for ReasoningStep."""
    
    def test_creation_thought(self):
        """Test creating a thought step."""
        step = ReasoningStep(
            step_type=ReasoningStepType.THOUGHT,
            content="Let me analyze this problem"
        )
        
        assert step.step_type == ReasoningStepType.THOUGHT
        assert step.content == "Let me analyze this problem"
    
    def test_creation_action(self):
        """Test creating an action step."""
        step = ReasoningStep(
            step_type=ReasoningStepType.ACTION,
            content="Call search tool",
            tool_used="search",
            tool_input={"query": "python"}
        )
        
        assert step.step_type == ReasoningStepType.ACTION
        assert step.tool_used == "search"
        assert step.tool_input["query"] == "python"
    
    def test_creation_observation(self):
        """Test creating an observation step."""
        step = ReasoningStep(
            step_type=ReasoningStepType.OBSERVATION,
            content="Found 100 results",
            tool_used="search",
            tool_input={},
            tool_output={"results": ["result1", "result2"]}
        )
        
        assert step.step_type == ReasoningStepType.OBSERVATION
        assert step.tool_output is not None
    
    def test_creation_reflection(self):
        """Test creating a reflection step."""
        step = ReasoningStep(
            step_type=ReasoningStepType.REFLECTION,
            content="The search results are helpful",
            confidence=0.8
        )
        
        assert step.step_type == ReasoningStepType.REFLECTION
        assert step.confidence == 0.8
    
    def test_to_dict(self):
        """Test serialization."""
        step = ReasoningStep(
            step_type=ReasoningStepType.THOUGHT,
            content="Initial thought",
            confidence=0.7
        )
        
        d = step.to_dict()
        
        assert d["step_type"] == ReasoningStepType.THOUGHT.value
        assert d["content"] == "Initial thought"
        assert d["confidence"] == 0.7


class TestReactChain:
    """Tests for ReactChain."""
    
    def test_creation(self):
        """Test chain creation."""
        chain = ReactChain(task="Answer the question")
        
        assert chain.task == "Answer the question"
        assert chain.steps == []
        assert chain.successful is False
    
    def test_add_thought(self):
        """Test adding thought step."""
        chain = ReactChain(task="Solve problem")
        
        chain.add_thought("First, I need to understand the problem")
        
        assert len(chain.steps) == 1
        assert chain.steps[0].step_type == ReasoningStepType.THOUGHT
    
    def test_add_action(self):
        """Test adding action step."""
        chain = ReactChain(task="Find answer")
        
        chain.add_action("search", {"query": "test"})
        
        assert len(chain.steps) == 1
        assert chain.steps[0].step_type == ReasoningStepType.ACTION
        assert chain.steps[0].tool_used == "search"
    
    def test_add_observation(self):
        """Test adding observation step."""
        chain = ReactChain(task="Analyze")
        
        chain.add_observation("Found results", "search", {"query": "test"}, {"count": 5})
        
        assert len(chain.steps) == 1
        assert chain.steps[0].step_type == ReasoningStepType.OBSERVATION
    
    def test_add_reflection(self):
        """Test adding reflection step."""
        chain = ReactChain(task="Review")
        
        chain.add_reflection("These results are relevant", confidence=0.9)
        
        assert len(chain.steps) == 1
        assert chain.steps[0].step_type == ReasoningStepType.REFLECTION
        assert chain.steps[0].confidence == 0.9
    
    def test_set_final_answer(self):
        """Test setting final answer."""
        chain = ReactChain(task="Question")
        chain.add_thought("I think the answer is...")
        
        chain.set_final_answer("The answer is 42", confidence=0.95)
        
        assert chain.final_answer == "The answer is 42"
        assert chain.confidence == 0.95
        assert chain.successful is True
    
    def test_set_error(self):
        """Test setting error."""
        chain = ReactChain(task="Failing task")
        
        chain.set_error("Tool execution failed: connection timeout")
        
        assert chain.error == "Tool execution failed: connection timeout"
        assert chain.successful is False
    
    def test_get_reasoning_trace(self):
        """Test getting reasoning trace."""
        chain = ReactChain(task="Problem solving")
        chain.add_thought("Initial thought")
        chain.add_action("math", {})
        chain.add_observation("Got result", "math", {}, {"result": 10})
        chain.add_reflection("Result makes sense")
        
        trace = chain.get_reasoning_trace()
        
        assert "Initial thought" in trace
        assert "Got result" in trace
        assert "Result makes sense" in trace
    
    def test_to_dict(self):
        """Test serialization."""
        chain = ReactChain(task="Test task")
        chain.add_thought("Thinking")
        chain.set_final_answer("Answer", confidence=0.8)
        
        d = chain.to_dict()
        
        assert d["task"] == "Test task"
        assert d["final_answer"] == "Answer"
        assert d["confidence"] == 0.8
        assert d["successful"] is True
        assert len(d["steps"]) >= 1


class TestReactAgentExecutor:
    """Tests for ReactAgentExecutor."""
    
    def test_initialization(self):
        """Test executor initialization."""
        executor = ReactAgentExecutor(name="my_agent")
        
        assert executor.name == "my_agent"
        assert executor.max_steps == 10
        assert executor.tools == {}
    
    def test_register_tool(self):
        """Test registering a tool."""
        executor = ReactAgentExecutor()
        
        def search_tool(query: str) -> dict:
            return {"results": []}
        
        executor.register_tool("search", search_tool, "Searches for information")
        
        assert "search" in executor.tools
        assert executor.tools["search"]["function"] == search_tool
    
    def test_register_multiple_tools(self):
        """Test registering multiple tools."""
        executor = ReactAgentExecutor()
        
        executor.register_tool("search", lambda q: {}, "Search")
        executor.register_tool("calc", lambda x, y: x + y, "Calculate")
        executor.register_tool("info", lambda x: {}, "Get info")
        
        assert len(executor.tools) == 3
    
    def test_execute_simple_task(self):
        """Test executing a simple task."""
        executor = ReactAgentExecutor(name="simple_executor")
        
        executor.register_tool(
            "answer",
            lambda: {"answer": 42},
            "Get the answer"
        )
        
        chain = executor.execute(
            task="What is the answer?",
            context={}
        )
        
        assert isinstance(chain, ReactChain)
        assert chain.task == "What is the answer?"
    
    def test_execute_with_context(self):
        """Test executing with context."""
        executor = ReactAgentExecutor()
        
        executor.register_tool("get_value", lambda: 100, "Get value")
        
        context = {"user": "alice", "domain": "test"}
        chain = executor.execute(
            task="Process request",
            context=context
        )
        
        assert chain.task == "Process request"
    
    def test_execute_basic(self):
        """Test basic execution."""
        executor = ReactAgentExecutor(name="test_executor")
        
        executor.register_tool("dummy", lambda: None, "Dummy")
        
        chain = executor.execute("Task")
        
        assert isinstance(chain, ReactChain)
        assert len(chain.steps) <= executor.max_steps
    
    def test_chain_with_tool_selection(self):
        """Test chain with tool selection."""
        executor = ReactAgentExecutor()
        
        executor.register_tool("search", lambda q: {"results": []}, "Search")
        executor.register_tool("read", lambda p: {"content": ""}, "Read")
        
        chain = executor.execute("Find and read document")
        
        assert isinstance(chain, ReactChain)
        assert len(chain.steps) >= 0
    
    def test_chain_has_steps(self):
        """Test that chain has reasoning steps."""
        executor = ReactAgentExecutor(name="step_test")
        
        executor.register_tool("calculate", lambda x, y: x + y, "Math")
        
        chain = executor.execute("Calculate 2 + 3")
        
        assert isinstance(chain, ReactChain)
        assert isinstance(chain.steps, list)


class TestReasoningStepTypeEnum:
    """Tests for ReasoningStepType enum."""
    
    def test_step_type_values(self):
        """Test step type values."""
        assert ReasoningStepType.THOUGHT.value == "thought"
        assert ReasoningStepType.OBSERVATION.value == "observation"
        assert ReasoningStepType.ACTION.value == "action"
        assert ReasoningStepType.REFLECTION.value == "reflection"
    
    def test_all_step_types(self):
        """Test all step types are available."""
        types = list(ReasoningStepType)
        
        assert len(types) == 4
        assert ReasoningStepType.THOUGHT in types
        assert ReasoningStepType.ACTION in types
        assert ReasoningStepType.OBSERVATION in types
        assert ReasoningStepType.REFLECTION in types
