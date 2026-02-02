"""
ReAct (Reasoning + Acting) Pattern Implementation

This module implements the ReAct pattern for agent planning and execution.
The ReAct pattern separates explicit Reasoning steps from Acting steps,
providing better transparency, debugging capability, and decision-making.

Reference: "ReAct: Synergizing Reasoning and Acting in Language Models"
https://arxiv.org/abs/2210.03629
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import logging


logger = logging.getLogger(__name__)


class ReActStepType(str, Enum):
    """Types of steps in the ReAct pattern."""

    THINK = "think"  # Reasoning step - internal thought
    ACT = "act"  # Acting step - tool call or action
    OBSERVE = "observe"  # Observation step - tool result
    CONCLUDE = "conclude"  # Final conclusion step


class ReActToolCall(str, Enum):
    """Tool actions available during acting phase."""

    SEARCH = "search"
    LOOKUP = "lookup"
    CALCULATE = "calculate"
    EXECUTE = "execute"
    PYTHON = "python"


@dataclass
class ReActStep:
    """
    A single step in the ReAct pattern execution.

    Attributes:
        step_type: Type of step (think, act, observe, conclude)
        content: The actual reasoning or action content
        tool_name: Name of tool used (if act step)
        tool_input: Input to the tool (if act step)
        observation: Result/observation from tool (if observe step)
        timestamp: When the step was executed
        reasoning: Optional explicit reasoning for this step
        confidence: Confidence score (0-1) for this decision
        step_id: Unique identifier for this step
    """

    step_type: ReActStepType
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    reasoning: Optional[str] = None
    confidence: float = 1.0
    step_id: str = field(default_factory=lambda: None)

    def __post_init__(self):
        """Generate step ID if not provided."""
        if self.step_id is None:
            import uuid

            self.step_id = str(uuid.uuid4())[:8]

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary representation."""
        return {
            "step_id": self.step_id,
            "step_type": self.step_type.value,
            "content": self.content,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "observation": self.observation,
            "timestamp": self.timestamp.isoformat(),
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }

    def to_json(self) -> str:
        """Convert step to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def think(
        cls,
        content: str,
        reasoning: Optional[str] = None,
        confidence: float = 1.0,
    ) -> "ReActStep":
        """Create a thinking (reasoning) step."""
        return cls(
            step_type=ReActStepType.THINK,
            content=content,
            reasoning=reasoning,
            confidence=confidence,
        )

    @classmethod
    def act(
        cls,
        tool_name: str,
        tool_input: Dict[str, Any],
        reasoning: Optional[str] = None,
    ) -> "ReActStep":
        """Create an acting (tool call) step."""
        return cls(
            step_type=ReActStepType.ACT,
            content=f"Call {tool_name} with {tool_input}",
            tool_name=tool_name,
            tool_input=tool_input,
            reasoning=reasoning,
        )

    @classmethod
    def observe(cls, observation: str, confidence: float = 1.0) -> "ReActStep":
        """Create an observation step."""
        return cls(
            step_type=ReActStepType.OBSERVE,
            content=observation,
            observation=observation,
            confidence=confidence,
        )

    @classmethod
    def conclude(cls, content: str, confidence: float = 1.0) -> "ReActStep":
        """Create a conclusion step."""
        return cls(
            step_type=ReActStepType.CONCLUDE,
            content=content,
            confidence=confidence,
        )


@dataclass
class ReActPlan:
    """
    A ReAct plan consisting of multiple reasoning and acting steps.

    Attributes:
        goal: The overall goal/task
        steps: Ordered list of ReActStep objects
        max_steps: Maximum number of steps allowed
        created_at: When the plan was created
        completed_at: When the plan finished executing
    """

    goal: str
    steps: List[ReActStep] = field(default_factory=list)
    max_steps: int = 10
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    def add_step(self, step: ReActStep) -> None:
        """Add a step to the plan."""
        if len(self.steps) >= self.max_steps:
            raise RuntimeError(f"Maximum steps ({self.max_steps}) reached")
        self.steps.append(step)

    def add_thinking(
        self, content: str, reasoning: Optional[str] = None
    ) -> ReActStep:
        """Add a thinking step."""
        step = ReActStep.think(content, reasoning)
        self.add_step(step)
        return step

    def add_action(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        reasoning: Optional[str] = None,
    ) -> ReActStep:
        """Add an acting step."""
        step = ReActStep.act(tool_name, tool_input, reasoning)
        self.add_step(step)
        return step

    def add_observation(
        self, observation: str, confidence: float = 1.0
    ) -> ReActStep:
        """Add an observation step."""
        step = ReActStep.observe(observation, confidence)
        self.add_step(step)
        return step

    def add_conclusion(self, content: str, confidence: float = 1.0) -> ReActStep:
        """Add a conclusion step."""
        step = ReActStep.conclude(content, confidence)
        self.add_step(step)
        return step

    def get_thinking_steps(self) -> List[ReActStep]:
        """Get all thinking steps."""
        return [s for s in self.steps if s.step_type == ReActStepType.THINK]

    def get_action_steps(self) -> List[ReActStep]:
        """Get all action steps."""
        return [s for s in self.steps if s.step_type == ReActStepType.ACT]

    def get_observation_steps(self) -> List[ReActStep]:
        """Get all observation steps."""
        return [s for s in self.steps if s.step_type == ReActStepType.OBSERVE]

    def get_reasoning_chain(self) -> List[str]:
        """Get chain of reasoning from all think steps."""
        return [s.content for s in self.get_thinking_steps()]

    def get_action_chain(self) -> List[Dict[str, Any]]:
        """Get chain of actions taken."""
        return [
            {
                "tool": s.tool_name,
                "input": s.tool_input,
                "reasoning": s.reasoning,
            }
            for s in self.get_action_steps()
        ]

    def get_final_answer(self) -> Optional[str]:
        """Get the final answer/conclusion."""
        conclusions = [s for s in self.steps if s.step_type == ReActStepType.CONCLUDE]
        return conclusions[-1].content if conclusions else None

    def mark_complete(self) -> None:
        """Mark plan as complete."""
        self.completed_at = datetime.now()

    def execution_time(self) -> Optional[float]:
        """Get total execution time in seconds."""
        if self.completed_at:
            delta = self.completed_at - self.created_at
            return delta.total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary."""
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "max_steps": self.max_steps,
            "step_count": len(self.steps),
            "created_at": self.created_at.isoformat(),
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "execution_time": self.execution_time(),
            "final_answer": self.get_final_answer(),
        }

    def to_json(self) -> str:
        """Convert plan to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def to_trajectory(self) -> str:
        """Convert plan to trajectory format for analysis."""
        trajectory = f"Goal: {self.goal}\n"
        trajectory += f"Steps: {len(self.steps)}/{self.max_steps}\n\n"

        for i, step in enumerate(self.steps, 1):
            trajectory += f"Step {i}: {step.step_type.value.upper()}\n"
            trajectory += f"  Content: {step.content}\n"
            if step.reasoning:
                trajectory += f"  Reasoning: {step.reasoning}\n"
            if step.observation:
                trajectory += f"  Observation: {step.observation}\n"
            trajectory += f"  Confidence: {step.confidence}\n\n"

        if self.completed_at:
            trajectory += f"Execution Time: {self.execution_time():.2f}s\n"

        return trajectory


@dataclass
class ReActExecutor:
    """
    Executor for ReAct pattern plans.

    Manages the execution of ReAct plans, coordinating between
    reasoning phases and acting phases.

    Attributes:
        max_iterations: Maximum iterations allowed
        tools: Dictionary of available tools
        verbose: Enable verbose logging
    """

    max_iterations: int = 10
    tools: Dict[str, Any] = field(default_factory=dict)
    verbose: bool = False

    def register_tool(self, name: str, tool_func: Any) -> None:
        """Register a tool for use during execution."""
        self.tools[name] = tool_func
        if self.verbose:
            logger.info(f"Registered tool: {name}")

    def execute_plan(self, plan: ReActPlan) -> ReActPlan:
        """
        Execute a ReAct plan.

        Args:
            plan: The ReActPlan to execute

        Returns:
            The executed plan with all steps populated

        Raises:
            RuntimeError: If execution fails or max iterations exceeded
        """
        iteration = 0
        while iteration < self.max_iterations and plan.steps[-1].step_type != ReActStepType.CONCLUDE:
            iteration += 1

            if self.verbose:
                logger.info(f"Iteration {iteration}")

            # Check if we need more thinking
            if (
                not plan.steps
                or plan.steps[-1].step_type in [ReActStepType.OBSERVE, ReActStepType.ACT]
            ):
                # Add thinking step (placeholder - would be filled by agent)
                plan.add_thinking(f"Iteration {iteration}: Deciding next action...")

            # Execute action if ready
            if plan.steps and plan.steps[-1].step_type == ReActStepType.THINK:
                last_think = plan.steps[-1]
                # Placeholder - would extract action from thinking
                # In real usage, this would be determined by LLM
                if "search" in last_think.content.lower():
                    plan.add_action("search", {"query": "information"})

            # Add observation for last action
            if plan.steps and plan.steps[-1].step_type == ReActStepType.ACT:
                action_step = plan.steps[-1]
                if action_step.tool_name in self.tools:
                    try:
                        tool_result = self.tools[action_step.tool_name](
                            **action_step.tool_input
                        )
                        plan.add_observation(str(tool_result))
                    except Exception as e:
                        plan.add_observation(f"Error: {str(e)}")
                else:
                    plan.add_observation(
                        f"Tool {action_step.tool_name} not available"
                    )

        if iteration >= self.max_iterations:
            logger.warning("Max iterations reached without conclusion")
            plan.add_conclusion("Reached maximum iterations without solution")

        plan.mark_complete()
        return plan

    def analyze_plan(self, plan: ReActPlan) -> Dict[str, Any]:
        """Analyze a completed plan for insights."""
        thinking_steps = plan.get_thinking_steps()
        action_steps = plan.get_action_steps()
        observation_steps = plan.get_observation_steps()

        avg_confidence = (
            sum(s.confidence for s in plan.steps) / len(plan.steps)
            if plan.steps
            else 0
        )

        return {
            "total_steps": len(plan.steps),
            "thinking_steps": len(thinking_steps),
            "action_steps": len(action_steps),
            "observation_steps": len(observation_steps),
            "average_confidence": avg_confidence,
            "execution_time": plan.execution_time(),
            "goal": plan.goal,
            "final_answer": plan.get_final_answer(),
            "reasoning_chain": plan.get_reasoning_chain(),
        }


def create_react_agent(goal: str, max_steps: int = 10) -> ReActPlan:
    """
    Create a new ReAct agent plan.

    Args:
        goal: The goal/task for the agent
        max_steps: Maximum steps allowed (default: 10)

    Returns:
        A new ReActPlan ready for execution
    """
    return ReActPlan(goal=goal, max_steps=max_steps)


__all__ = [
    "ReActStepType",
    "ReActToolCall",
    "ReActStep",
    "ReActPlan",
    "ReActExecutor",
    "create_react_agent",
]
