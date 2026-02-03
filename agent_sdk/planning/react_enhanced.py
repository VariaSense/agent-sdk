"""
React Pattern Enhancement: Explicit Reason→Act→Observe steps for agents.

Enhances the React pattern with structured reasoning, action selection, and
observation loops for more transparent and controllable agent behavior.
"""

from typing import Any, Dict, List, Optional, Tuple, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
import asyncio


class ReactStep(str, Enum):
    """Steps in the React pattern."""
    REASON = "reason"
    ACT = "act"
    OBSERVE = "observe"


@dataclass
class Thought:
    """Represents a thought during reasoning phase."""
    content: str
    reasoning_type: str  # "analysis", "planning", "hypothesis", etc.
    confidence: float = 0.5  # 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "content": self.content,
            "type": self.reasoning_type,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class Action:
    """Represents an action taken by the agent."""
    tool_name: str
    parameters: Dict[str, Any]
    action_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "tool": self.tool_name,
            "parameters": self.parameters,
            "action_id": self.action_id,
            "metadata": self.metadata,
        }


@dataclass
class Observation:
    """Represents an observation from executing an action."""
    action_id: str
    result: Any
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "action_id": self.action_id,
            "result": self.result,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class ReactCycle:
    """Complete React cycle: Reason→Act→Observe."""
    cycle_id: str
    thoughts: List[Thought] = field(default_factory=list)
    action: Optional[Action] = None
    observation: Optional[Observation] = None
    step_number: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_thought(self, thought: Thought) -> None:
        """Add a thought during reasoning."""
        self.thoughts.append(thought)

    def set_action(self, action: Action) -> None:
        """Set the action for this cycle."""
        self.action = action

    def set_observation(self, observation: Observation) -> None:
        """Set the observation from the action."""
        self.observation = observation

    def is_complete(self) -> bool:
        """Check if cycle is complete (has observation)."""
        return self.observation is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "cycle_id": self.cycle_id,
            "step": self.step_number,
            "thoughts": [t.to_dict() for t in self.thoughts],
            "action": self.action.to_dict() if self.action else None,
            "observation": self.observation.to_dict() if self.observation else None,
            "metadata": self.metadata,
        }


class ReasoningEngine:
    """Handles the reasoning phase of React pattern."""

    def __init__(self, context_size: int = 10):
        """
        Initialize reasoning engine.

        Args:
            context_size: Number of previous cycles to consider
        """
        self.context_size = context_size
        self.reasoning_history: List[Thought] = []

    async def reason(
        self,
        prompt: str,
        context: Optional[str] = None,
    ) -> List[Thought]:
        """
        Generate thoughts during reasoning phase.

        Args:
            prompt: Current prompt/question
            context: Optional context from previous cycles

        Returns:
            List of thoughts generated
        """
        thoughts = []

        # Initial analysis thought
        thoughts.append(Thought(
            content=f"Analyzing: {prompt[:100]}...",
            reasoning_type="analysis",
            confidence=0.8,
        ))

        # Planning thought
        thoughts.append(Thought(
            content="Planning approach to solve the problem",
            reasoning_type="planning",
            confidence=0.7,
        ))

        if context:
            # Contextual thought
            thoughts.append(Thought(
                content=f"Considering previous context",
                reasoning_type="contextual",
                confidence=0.6,
            ))

        # Add to history
        self.reasoning_history.extend(thoughts)
        if len(self.reasoning_history) > self.context_size:
            self.reasoning_history = self.reasoning_history[-self.context_size:]

        return thoughts

    def get_reasoning_summary(self) -> str:
        """Get summary of reasoning history."""
        if not self.reasoning_history:
            return "No reasoning yet"

        summary = "\n".join([
            f"- {t.reasoning_type}: {t.content} (confidence: {t.confidence:.2f})"
            for t in self.reasoning_history[-5:]
        ])
        return summary


class ActionSelector:
    """Selects actions based on reasoning."""

    def __init__(self, available_tools: Dict[str, Any]):
        """
        Initialize action selector.

        Args:
            available_tools: Dict of tool_name -> tool_callable
        """
        self.available_tools = available_tools
        self.action_history: List[Action] = []

    async def select_action(
        self,
        thoughts: List[Thought],
        observation_history: List[Observation] = None,
    ) -> Optional[Action]:
        """
        Select next action based on thoughts.

        Args:
            thoughts: List of thoughts from reasoning
            observation_history: Previous observations

        Returns:
            Selected action or None
        """
        if not thoughts:
            return None

        # Simple heuristic: find highest confidence thought
        best_thought = max(thoughts, key=lambda t: t.confidence)

        # Map thought to action
        if "search" in best_thought.content.lower():
            action = Action(
                tool_name="search",
                parameters={"query": best_thought.content},
            )
        elif "calculate" in best_thought.content.lower():
            action = Action(
                tool_name="calculator",
                parameters={"expression": best_thought.content},
            )
        else:
            # Default to first available tool
            if self.available_tools:
                tool_name = list(self.available_tools.keys())[0]
                action = Action(
                    tool_name=tool_name,
                    parameters={"input": best_thought.content},
                )
            else:
                return None

        # Assign ID
        action.action_id = f"action_{len(self.action_history)}"

        self.action_history.append(action)
        return action

    def get_available_tools(self) -> List[str]:
        """Get list of available tools."""
        return list(self.available_tools.keys())


class ObservationProcessor:
    """Processes observations from actions."""

    def __init__(self):
        self.observation_history: List[Observation] = []
        self.success_count = 0
        self.failure_count = 0

    async def process_observation(
        self,
        action: Action,
        result: Any,
        error: Optional[str] = None,
    ) -> Observation:
        """
        Process observation from action execution.

        Args:
            action: The action that was executed
            result: Result from action execution
            error: Optional error message

        Returns:
            Observation object
        """
        success = error is None

        observation = Observation(
            action_id=action.action_id,
            result=result,
            success=success,
            error=error,
        )

        self.observation_history.append(observation)

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        return observation

    def should_continue(self) -> bool:
        """Determine if agent should continue or stop."""
        # Stop if last observation was successful
        if self.observation_history:
            last = self.observation_history[-1]
            return not last.success or last.error is not None

        return True

    def get_observation_summary(self) -> str:
        """Get summary of observations."""
        if not self.observation_history:
            return "No observations yet"

        success_rate = (
            self.success_count / len(self.observation_history)
            if self.observation_history else 0
        )
        return f"Success rate: {success_rate:.2%} ({self.success_count}/{self.success_count + self.failure_count})"


class EnhancedReactAgent:
    """Agent using enhanced React pattern with explicit steps."""

    def __init__(
        self,
        available_tools: Dict[str, Any],
        max_cycles: int = 5,
    ):
        """
        Initialize React agent.

        Args:
            available_tools: Dict of available tools
            max_cycles: Maximum React cycles to execute
        """
        self.available_tools = available_tools
        self.max_cycles = max_cycles
        self.reasoning_engine = ReasoningEngine()
        self.action_selector = ActionSelector(available_tools)
        self.observation_processor = ObservationProcessor()
        self.cycles: List[ReactCycle] = []

    async def run(
        self,
        prompt: str,
        context: Optional[str] = None,
    ) -> AsyncIterator[Tuple[ReactStep, Any]]:
        """
        Run React loop with explicit step outputs.

        Args:
            prompt: Input prompt
            context: Optional context

        Yields:
            Tuples of (step_type, data)
        """
        cycle_count = 0

        while cycle_count < self.max_cycles:
            cycle_id = f"cycle_{cycle_count}"
            cycle = ReactCycle(cycle_id=cycle_id, step_number=cycle_count)

            # REASON step
            yield (ReactStep.REASON, {"cycle_id": cycle_id, "status": "starting"})

            thoughts = await self.reasoning_engine.reason(prompt, context)
            for thought in thoughts:
                cycle.add_thought(thought)
                yield (ReactStep.REASON, thought.to_dict())

            # ACT step
            yield (ReactStep.ACT, {"cycle_id": cycle_id, "status": "starting"})

            action = await self.action_selector.select_action(
                thoughts,
                self.observation_processor.observation_history,
            )

            if action is None:
                yield (ReactStep.ACT, {"error": "No action selected"})
                break

            cycle.set_action(action)
            yield (ReactStep.ACT, action.to_dict())

            # OBSERVE step
            yield (ReactStep.OBSERVE, {"cycle_id": cycle_id, "status": "starting"})

            # Execute action
            result = None
            error = None

            try:
                if action.tool_name in self.available_tools:
                    tool = self.available_tools[action.tool_name]
                    if asyncio.iscoroutinefunction(tool):
                        result = await tool(**action.parameters)
                    else:
                        result = tool(**action.parameters)
            except Exception as e:
                error = str(e)

            # Process observation
            observation = await self.observation_processor.process_observation(
                action,
                result,
                error,
            )

            cycle.set_observation(observation)
            yield (ReactStep.OBSERVE, observation.to_dict())

            self.cycles.append(cycle)
            cycle_count += 1

            # Check stopping condition
            if not self.observation_processor.should_continue():
                break

    def get_cycles(self) -> List[ReactCycle]:
        """Get all completed cycles."""
        return self.cycles.copy()

    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        return {
            "total_cycles": len(self.cycles),
            "complete_cycles": sum(1 for c in self.cycles if c.is_complete()),
            "thoughts": self.reasoning_engine.get_reasoning_summary(),
            "observations": self.observation_processor.get_observation_summary(),
            "tools_used": list(set(
                c.action.tool_name
                for c in self.cycles
                if c.action
            )),
        }
