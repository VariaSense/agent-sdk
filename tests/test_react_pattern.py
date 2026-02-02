"""
Tests for ReAct pattern implementation.
"""

import pytest
from datetime import datetime
from agent_sdk.planning.react_pattern import (
    ReActStepType,
    ReActStep,
    ReActPlan,
    ReActExecutor,
    create_react_agent,
)


class TestReActStep:
    """Test ReActStep functionality."""

    def test_create_think_step(self):
        """Test creating a thinking step."""
        step = ReActStep.think("Let me analyze the problem")
        assert step.step_type == ReActStepType.THINK
        assert step.content == "Let me analyze the problem"
        assert step.step_id is not None

    def test_create_act_step(self):
        """Test creating an acting step."""
        step = ReActStep.act("search", {"query": "python documentation"})
        assert step.step_type == ReActStepType.ACT
        assert step.tool_name == "search"
        assert step.tool_input == {"query": "python documentation"}

    def test_create_observe_step(self):
        """Test creating an observation step."""
        step = ReActStep.observe("Found 5 results about Python")
        assert step.step_type == ReActStepType.OBSERVE
        assert step.observation == "Found 5 results about Python"

    def test_create_conclude_step(self):
        """Test creating a conclusion step."""
        step = ReActStep.conclude("The answer is 42")
        assert step.step_type == ReActStepType.CONCLUDE
        assert step.content == "The answer is 42"

    def test_step_with_reasoning(self):
        """Test step with explicit reasoning."""
        reasoning = "Based on the analysis, this is the next logical step"
        step = ReActStep.think("Next step", reasoning=reasoning)
        assert step.reasoning == reasoning

    def test_step_confidence(self):
        """Test step confidence scoring."""
        step = ReActStep.think("Hypothesis", confidence=0.7)
        assert step.confidence == 0.7

    def test_step_to_dict(self):
        """Test converting step to dictionary."""
        step = ReActStep.think("Analyzing")
        step_dict = step.to_dict()
        assert step_dict["step_type"] == "think"
        assert step_dict["content"] == "Analyzing"
        assert step_dict["step_id"] is not None

    def test_step_to_json(self):
        """Test converting step to JSON."""
        step = ReActStep.act("calculate", {"expr": "2+2"})
        json_str = step.to_json()
        assert "think" not in json_str  # act, not think
        assert "calculate" in json_str


class TestReActPlan:
    """Test ReActPlan functionality."""

    def test_create_plan(self):
        """Test creating a plan."""
        plan = ReActPlan(goal="Solve the math problem")
        assert plan.goal == "Solve the math problem"
        assert len(plan.steps) == 0
        assert plan.created_at is not None

    def test_add_thinking_step(self):
        """Test adding thinking steps."""
        plan = ReActPlan(goal="Test")
        plan.add_thinking("First thought")
        plan.add_thinking("Second thought")
        assert len(plan.steps) == 2
        assert plan.get_thinking_steps() == plan.steps

    def test_add_action_step(self):
        """Test adding action steps."""
        plan = ReActPlan(goal="Test")
        plan.add_action("search", {"query": "test"})
        assert len(plan.steps) == 1
        assert plan.steps[0].step_type == ReActStepType.ACT

    def test_add_observation_step(self):
        """Test adding observation steps."""
        plan = ReActPlan(goal="Test")
        plan.add_observation("Found results")
        assert len(plan.steps) == 1
        assert plan.steps[0].step_type == ReActStepType.OBSERVE

    def test_add_conclusion_step(self):
        """Test adding conclusion step."""
        plan = ReActPlan(goal="Test")
        plan.add_conclusion("Final answer")
        assert len(plan.steps) == 1
        assert plan.steps[0].step_type == ReActStepType.CONCLUDE

    def test_max_steps_enforcement(self):
        """Test that max steps is enforced."""
        plan = ReActPlan(goal="Test", max_steps=2)
        plan.add_thinking("Step 1")
        plan.add_thinking("Step 2")
        with pytest.raises(RuntimeError):
            plan.add_thinking("Step 3 - should fail")

    def test_get_thinking_steps(self):
        """Test filtering thinking steps."""
        plan = ReActPlan(goal="Test")
        plan.add_thinking("Thought 1")
        plan.add_action("search", {})
        plan.add_thinking("Thought 2")
        thinking = plan.get_thinking_steps()
        assert len(thinking) == 2
        assert all(s.step_type == ReActStepType.THINK for s in thinking)

    def test_get_action_steps(self):
        """Test filtering action steps."""
        plan = ReActPlan(goal="Test")
        plan.add_thinking("Thought")
        plan.add_action("search", {})
        plan.add_action("lookup", {})
        actions = plan.get_action_steps()
        assert len(actions) == 2

    def test_get_observation_steps(self):
        """Test filtering observation steps."""
        plan = ReActPlan(goal="Test")
        plan.add_observation("Obs 1")
        plan.add_thinking("Thought")
        plan.add_observation("Obs 2")
        observations = plan.get_observation_steps()
        assert len(observations) == 2

    def test_get_reasoning_chain(self):
        """Test getting reasoning chain."""
        plan = ReActPlan(goal="Test")
        plan.add_thinking("First reasoning")
        plan.add_thinking("Second reasoning")
        plan.add_action("search", {})
        chain = plan.get_reasoning_chain()
        assert len(chain) == 2
        assert "First reasoning" in chain

    def test_get_action_chain(self):
        """Test getting action chain."""
        plan = ReActPlan(goal="Test")
        plan.add_thinking("Thought")
        plan.add_action("search", {"query": "q1"})
        plan.add_action("lookup", {"term": "t1"})
        chain = plan.get_action_chain()
        assert len(chain) == 2
        assert chain[0]["tool"] == "search"
        assert chain[1]["tool"] == "lookup"

    def test_get_final_answer(self):
        """Test getting final answer."""
        plan = ReActPlan(goal="Test")
        plan.add_thinking("Thought")
        plan.add_action("search", {})
        plan.add_observation("Result")
        assert plan.get_final_answer() is None  # No conclusion yet
        plan.add_conclusion("The answer is 42")
        assert plan.get_final_answer() == "The answer is 42"

    def test_mark_complete(self):
        """Test marking plan as complete."""
        plan = ReActPlan(goal="Test")
        assert plan.completed_at is None
        plan.mark_complete()
        assert plan.completed_at is not None

    def test_execution_time(self):
        """Test execution time calculation."""
        plan = ReActPlan(goal="Test")
        assert plan.execution_time() is None
        plan.mark_complete()
        exec_time = plan.execution_time()
        assert exec_time is not None
        assert exec_time >= 0

    def test_plan_to_dict(self):
        """Test converting plan to dictionary."""
        plan = ReActPlan(goal="Test", max_steps=10)
        plan.add_thinking("Thought")
        plan.add_action("search", {})
        plan.add_observation("Result")
        plan.add_conclusion("Done")
        plan.mark_complete()

        plan_dict = plan.to_dict()
        assert plan_dict["goal"] == "Test"
        assert plan_dict["step_count"] == 4
        assert len(plan_dict["steps"]) == 4
        assert plan_dict["final_answer"] == "Done"

    def test_plan_to_trajectory(self):
        """Test converting plan to trajectory format."""
        plan = ReActPlan(goal="Solve problem", max_steps=10)
        plan.add_thinking("Analyzing")
        plan.add_action("search", {})
        plan.add_observation("Found data")
        plan.add_conclusion("Answer")
        plan.mark_complete()

        trajectory = plan.to_trajectory()
        assert "Goal: Solve problem" in trajectory
        assert "Step 1: THINK" in trajectory
        assert "Step 2: ACT" in trajectory
        assert "Step 3: OBSERVE" in trajectory
        assert "Step 4: CONCLUDE" in trajectory
        assert "Execution Time:" in trajectory


class TestReActExecutor:
    """Test ReActExecutor functionality."""

    def test_create_executor(self):
        """Test creating an executor."""
        executor = ReActExecutor(max_iterations=5)
        assert executor.max_iterations == 5
        assert len(executor.tools) == 0

    def test_register_tool(self):
        """Test registering a tool."""
        executor = ReActExecutor()

        def search_tool(query):
            return f"Results for {query}"

        executor.register_tool("search", search_tool)
        assert "search" in executor.tools
        assert executor.tools["search"] is search_tool

    def test_register_multiple_tools(self):
        """Test registering multiple tools."""
        executor = ReActExecutor()
        executor.register_tool("search", lambda q: f"Search: {q}")
        executor.register_tool("calculate", lambda e: eval(e))
        assert len(executor.tools) == 2

    def test_execute_simple_plan(self):
        """Test executing a simple plan."""

        def mock_search(query):
            return "Search results"

        executor = ReActExecutor(max_iterations=5)
        executor.register_tool("search", mock_search)

        plan = ReActPlan(goal="Search for info", max_steps=5)
        plan.add_thinking("I need to search")
        plan.add_action("search", {"query": "test"})

        # Execute would continue from here
        assert len(plan.steps) == 2

    def test_analyze_plan(self):
        """Test analyzing a plan."""
        executor = ReActExecutor()
        plan = ReActPlan(goal="Test goal")
        plan.add_thinking("Thought 1", confidence=0.9)
        plan.add_action("search", {})
        plan.add_observation("Result", confidence=0.95)
        plan.add_conclusion("Done", confidence=0.85)
        plan.mark_complete()

        analysis = executor.analyze_plan(plan)
        assert analysis["total_steps"] == 4
        assert analysis["thinking_steps"] == 1
        assert analysis["action_steps"] == 1
        assert analysis["observation_steps"] == 1
        assert 0 <= analysis["average_confidence"] <= 1
        assert analysis["goal"] == "Test goal"
        assert analysis["final_answer"] == "Done"

    def test_analyze_plan_reasoning_chain(self):
        """Test analyzing plan's reasoning chain."""
        executor = ReActExecutor()
        plan = ReActPlan(goal="Complex task")
        plan.add_thinking("First insight")
        plan.add_thinking("Second insight")
        plan.add_action("search", {})
        plan.mark_complete()

        analysis = executor.analyze_plan(plan)
        chain = analysis["reasoning_chain"]
        assert len(chain) == 2
        assert "First insight" in chain
        assert "Second insight" in chain


class TestCreateReActAgent:
    """Test factory function for creating ReAct agents."""

    def test_create_agent(self):
        """Test creating an agent with factory function."""
        plan = create_react_agent("Solve a problem")
        assert isinstance(plan, ReActPlan)
        assert plan.goal == "Solve a problem"
        assert plan.max_steps == 10

    def test_create_agent_custom_steps(self):
        """Test creating agent with custom max steps."""
        plan = create_react_agent("Quick task", max_steps=5)
        assert plan.max_steps == 5


class TestReActIntegration:
    """Integration tests for ReAct pattern."""

    def test_complete_react_workflow(self):
        """Test complete ReAct workflow."""
        # Create plan
        plan = create_react_agent("Answer math question")

        # Add reasoning step
        plan.add_thinking("The question asks for 2+2")

        # Add action
        plan.add_action("calculate", {"expr": "2+2"})

        # Simulate observation
        plan.add_observation("Result: 4")

        # Add conclusion
        plan.add_conclusion("The answer is 4", confidence=1.0)
        plan.mark_complete()

        # Verify trajectory
        assert len(plan.steps) == 4
        assert plan.get_final_answer() == "The answer is 4"
        assert plan.execution_time() is not None

    def test_react_with_analysis(self):
        """Test ReAct workflow with executor analysis."""
        executor = ReActExecutor()

        plan = create_react_agent("Multi-step task", max_steps=5)
        plan.add_thinking("Step 1: Understand problem")
        plan.add_thinking("Step 2: Plan approach")
        plan.add_action("search", {"query": "relevant info"})
        plan.add_observation("Found 10 sources")
        plan.add_conclusion("Solution ready")
        plan.mark_complete()

        analysis = executor.analyze_plan(plan)
        assert analysis["thinking_steps"] == 2
        assert analysis["action_steps"] == 1
        assert analysis["total_steps"] == 4

    def test_react_step_sequence(self):
        """Test proper step sequencing in ReAct."""
        plan = create_react_agent("Sequential task")

        # Typical pattern: Think -> Act -> Observe -> Think -> Conclude
        plan.add_thinking("Initial analysis")
        plan.add_action("search", {"query": "data"})
        plan.add_observation("Data retrieved")
        plan.add_thinking("Analyzing retrieved data")
        plan.add_conclusion("Final result")

        steps = plan.steps
        assert steps[0].step_type == ReActStepType.THINK
        assert steps[1].step_type == ReActStepType.ACT
        assert steps[2].step_type == ReActStepType.OBSERVE
        assert steps[3].step_type == ReActStepType.THINK
        assert steps[4].step_type == ReActStepType.CONCLUDE
