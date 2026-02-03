"""React (Reasoning + Acting) agent implementation."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import json


class ReasoningStepType(Enum):
    """Types of reasoning steps."""
    
    THOUGHT = "thought"              # Internal reasoning
    OBSERVATION = "observation"      # Observation from tool
    ACTION = "action"                # Decision to take action
    REFLECTION = "reflection"        # Reflection on results


@dataclass
class ReasoningStep:
    """A single step in reasoning."""
    
    step_type: ReasoningStepType
    content: str
    tool_used: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Any] = None
    confidence: float = 1.0
    reasoning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_type": self.step_type.value,
            "content": self.content,
            "tool_used": self.tool_used,
            "tool_input": self.tool_input,
            "tool_output": self.tool_output,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


@dataclass
class ReactChain:
    """A complete React reasoning chain."""
    
    task: str
    steps: List[ReasoningStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    confidence: float = 1.0
    successful: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_step(self, step: ReasoningStep) -> None:
        """Add a reasoning step."""
        self.steps.append(step)
    
    def add_thought(self, content: str, reasoning: Optional[str] = None) -> None:
        """Add a thought step."""
        step = ReasoningStep(
            step_type=ReasoningStepType.THOUGHT,
            content=content,
            reasoning=reasoning
        )
        self.add_step(step)
    
    def add_observation(self, content: str, tool_used: str,
                       tool_input: Dict[str, Any],
                       tool_output: Any) -> None:
        """Add an observation from tool execution."""
        step = ReasoningStep(
            step_type=ReasoningStepType.OBSERVATION,
            content=content,
            tool_used=tool_used,
            tool_input=tool_input,
            tool_output=tool_output
        )
        self.add_step(step)
    
    def add_action(self, tool_name: str, tool_input: Dict[str, Any]) -> None:
        """Record action decision."""
        step = ReasoningStep(
            step_type=ReasoningStepType.ACTION,
            content=f"Calling tool: {tool_name}",
            tool_used=tool_name,
            tool_input=tool_input
        )
        self.add_step(step)
    
    def add_reflection(self, content: str, confidence: float = 1.0) -> None:
        """Add a reflection step."""
        step = ReasoningStep(
            step_type=ReasoningStepType.REFLECTION,
            content=content,
            confidence=confidence
        )
        self.add_step(step)
    
    def set_final_answer(self, answer: str, confidence: float = 1.0) -> None:
        """Set final answer."""
        self.final_answer = answer
        self.confidence = confidence
        self.successful = True
    
    def set_error(self, error: str) -> None:
        """Record error."""
        self.error = error
        self.successful = False
    
    def get_reasoning_trace(self) -> str:
        """Get formatted reasoning trace."""
        trace = f"Task: {self.task}\n\n"
        
        for i, step in enumerate(self.steps, 1):
            trace += f"Step {i} ({step.step_type.value.upper()}):\n"
            trace += f"{step.content}\n"
            
            if step.tool_used:
                trace += f"Tool: {step.tool_used}\n"
            if step.tool_input:
                trace += f"Input: {json.dumps(step.tool_input, indent=2)}\n"
            if step.tool_output:
                trace += f"Output: {step.tool_output}\n"
            if step.reasoning:
                trace += f"Reasoning: {step.reasoning}\n"
            
            trace += "\n"
        
        if self.final_answer:
            trace += f"Final Answer: {self.final_answer}\n"
            trace += f"Confidence: {self.confidence:.2%}\n"
        
        if self.error:
            trace += f"Error: {self.error}\n"
        
        return trace
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task": self.task,
            "steps": [step.to_dict() for step in self.steps],
            "final_answer": self.final_answer,
            "confidence": self.confidence,
            "successful": self.successful,
            "error": self.error,
            "metadata": self.metadata,
            "step_count": len(self.steps)
        }


class ReactAgentExecutor:
    """Executes React (Reasoning + Acting) agent pattern."""
    
    def __init__(self, name: str = "react_agent"):
        """Initialize React executor.
        
        Args:
            name: Agent name
        """
        self.name = name
        self.tools: Dict[str, Any] = {}
        self.max_steps: int = 10
        self.thought_prompt_template = """Given the task: {task}

Current chain of thought:
{chain}

What should be the next step? Think about:
1. What do we know so far?
2. What's still unclear?
3. What action should we take?
4. Why is this action necessary?"""
        
        self.action_prompt_template = """Based on the reasoning so far, which tool should we use?
Available tools: {tools}

The tool should help us: {reasoning}
Return the tool name and input."""
    
    def register_tool(self, tool_name: str, tool_fn: Any,
                     description: Optional[str] = None) -> None:
        """Register a tool.
        
        Args:
            tool_name: Name of tool
            tool_fn: Tool function
            description: Tool description
        """
        self.tools[tool_name] = {
            "function": tool_fn,
            "description": description or tool_name
        }
    
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None,
               verbose: bool = False) -> ReactChain:
        """Execute task using React pattern.
        
        Args:
            task: Task to execute
            context: Context information
            verbose: Print reasoning steps
        
        Returns:
            React chain with full reasoning trace
        """
        chain = ReactChain(task=task)
        context = context or {}
        
        step_count = 0
        while step_count < self.max_steps and not chain.successful:
            step_count += 1
            
            try:
                # Phase 1: Thought - Reason about task
                thought = self._generate_thought(task, chain, context)
                if thought:
                    chain.add_thought(thought["content"], thought.get("reasoning"))
                    if verbose:
                        print(f"\n💭 Thought: {thought['content']}")
                
                # Phase 2: Action - Decide what to do
                action = self._select_action(task, chain, context)
                if action is None:
                    # No action needed, generate final answer
                    chain.set_final_answer(
                        self._generate_final_answer(task, chain, context),
                        confidence=0.8
                    )
                    break
                
                if verbose:
                    print(f"🔧 Action: {action['tool']}")
                    print(f"   Input: {action['input']}")
                
                # Phase 3: Observation - Execute action
                try:
                    tool_fn = self.tools[action["tool"]]["function"]
                    tool_output = tool_fn(**action["input"])
                    chain.add_observation(
                        f"Executed {action['tool']}",
                        tool_used=action["tool"],
                        tool_input=action["input"],
                        tool_output=tool_output
                    )
                    
                    if verbose:
                        print(f"📊 Result: {tool_output}")
                    
                except Exception as e:
                    chain.set_error(f"Tool execution failed: {str(e)}")
                    if verbose:
                        print(f"❌ Error: {str(e)}")
                    break
                
                # Phase 4: Reflection - Assess result
                reflection = self._reflect_on_result(
                    task, chain, tool_output, context
                )
                if reflection:
                    chain.add_reflection(
                        reflection["content"],
                        reflection.get("confidence", 1.0)
                    )
                    if verbose:
                        print(f"🤔 Reflection: {reflection['content']}")
                
            except Exception as e:
                chain.set_error(f"Execution error: {str(e)}")
                break
        
        if step_count >= self.max_steps and not chain.successful:
            chain.set_error(f"Max steps ({self.max_steps}) reached")
        
        return chain
    
    def _generate_thought(self, task: str, chain: ReactChain,
                         context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate a thought about the task.
        
        Args:
            task: Current task
            chain: Current reasoning chain
            context: Context
        
        Returns:
            Thought dict or None
        """
        # In real implementation, would use LLM to generate thought
        if not chain.steps:
            return {
                "content": f"Starting task: {task}",
                "reasoning": "Need to break down the task and identify next steps"
            }
        
        return None
    
    def _select_action(self, task: str, chain: ReactChain,
                      context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Select next action.
        
        Args:
            task: Current task
            chain: Current reasoning chain
            context: Context
        
        Returns:
            Action dict with tool name and input, or None if done
        """
        # In real implementation, would use LLM to select action
        if len(chain.steps) > 2:
            # No more actions for this simple example
            return None
        
        # Default: call first available tool
        if self.tools:
            tool_name = list(self.tools.keys())[0]
            return {
                "tool": tool_name,
                "input": {"query": task}
            }
        
        return None
    
    def _reflect_on_result(self, task: str, chain: ReactChain,
                          result: Any, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Reflect on tool result.
        
        Args:
            task: Current task
            chain: Current reasoning chain
            result: Tool result
            context: Context
        
        Returns:
            Reflection dict or None
        """
        # In real implementation, would use LLM for reflection
        return None
    
    def _generate_final_answer(self, task: str, chain: ReactChain,
                              context: Dict[str, Any]) -> str:
        """Generate final answer.
        
        Args:
            task: Current task
            chain: Current reasoning chain
            context: Context
        
        Returns:
            Final answer string
        """
        # In real implementation, would use LLM for answer generation
        if chain.steps:
            last_step = chain.steps[-1]
            if last_step.tool_output:
                return str(last_step.tool_output)
        
        return f"Completed task: {task}"
    
    def get_chain_summary(self, chain: ReactChain) -> Dict[str, Any]:
        """Get summary of reasoning chain."""
        return {
            "task": chain.task,
            "step_count": len(chain.steps),
            "successful": chain.successful,
            "final_answer": chain.final_answer,
            "confidence": chain.confidence,
            "reasoning_trace": chain.get_reasoning_trace()
        }
