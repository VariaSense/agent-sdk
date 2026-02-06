"""
Parallel Tool Execution: Execute multiple tools concurrently with dependency handling.

Enables concurrent tool calls while respecting dependencies, improving throughput
and reducing latency for multi-step agent workflows.
"""

from typing import Any, Dict, List, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import inspect
import uuid


class DependencyType(str, Enum):
    """Types of dependencies between tools."""
    SEQUENTIAL = "sequential"  # Must run after
    PARALLEL = "parallel"  # Can run in parallel
    CONDITIONAL = "conditional"  # Run if condition met


@dataclass
class ToolExecution:
    """Represents a tool execution."""
    tool_id: str
    tool_name: str
    parameters: Dict[str, Any]
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: Optional[str] = None
    start_time: float = 0.0
    end_time: float = 0.0
    dependencies: List[str] = field(default_factory=list)

    def duration(self) -> float:
        """Get execution duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "execution_id": self.execution_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "duration": self.duration(),
            "dependencies": self.dependencies,
        }


@dataclass
class ExecutionDependency:
    """Defines a dependency between tool executions."""
    source_tool: str  # Tool that must complete first
    target_tool: str  # Tool that depends on source
    dependency_type: DependencyType = DependencyType.SEQUENTIAL
    condition: Optional[Callable[[Any], bool]] = None

    def is_satisfied(self, source_result: Any) -> bool:
        """Check if dependency is satisfied."""
        if self.dependency_type == DependencyType.PARALLEL:
            return True
        if self.condition:
            return self.condition(source_result)
        return True


class DependencyGraph:
    """Graph of tool dependencies."""

    def __init__(self):
        self.dependencies: Dict[str, List[ExecutionDependency]] = {}
        self.tools: Set[str] = set()

    def add_tool(self, tool_id: str) -> None:
        """Add a tool to the graph."""
        self.tools.add(tool_id)
        if tool_id not in self.dependencies:
            self.dependencies[tool_id] = []

    def add_dependency(self, dependency: ExecutionDependency) -> None:
        """Add a dependency."""
        if dependency.target_tool not in self.dependencies:
            self.dependencies[dependency.target_tool] = []
        self.dependencies[dependency.target_tool].append(dependency)

    def get_ready_tools(
        self,
        completed: Dict[str, ToolExecution],
    ) -> List[str]:
        """Get tools that are ready to execute."""
        ready = []

        for tool_id in self.tools:
            # Skip if already completed
            if tool_id in completed:
                continue

            # Check dependencies
            deps = self.dependencies.get(tool_id, [])
            all_ready = True

            for dep in deps:
                # Dependency must be completed
                if dep.source_tool not in completed:
                    all_ready = False
                    break

                # Check condition if present
                if dep.condition:
                    source_result = completed[dep.source_tool].result
                    if not dep.condition(source_result):
                        all_ready = False
                        break

            if all_ready:
                ready.append(tool_id)

        return ready

    def get_all_dependencies(self, tool_id: str) -> Set[str]:
        """Get all transitive dependencies for a tool."""
        deps = set()
        to_process = [tool_id]

        while to_process:
            current = to_process.pop()
            for dep in self.dependencies.get(current, []):
                if dep.source_tool not in deps:
                    deps.add(dep.source_tool)
                    to_process.append(dep.source_tool)

        return deps


class ParallelToolExecutor:
    """Executes tools in parallel respecting dependencies."""

    def __init__(self, available_tools: Dict[str, Callable]):
        """
        Initialize executor.

        Args:
            available_tools: Dict of tool_name -> tool_callable
        """
        self.available_tools = available_tools
        self.dependency_graph = DependencyGraph()
        self.executions: Dict[str, ToolExecution] = {}
        self.execution_queue: List[ToolExecution] = []

    def add_tool_execution(
        self,
        tool_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        dependencies: List[str] = None,
    ) -> ToolExecution:
        """Add a tool execution to the queue."""
        execution = ToolExecution(
            tool_id=tool_id,
            tool_name=tool_name,
            parameters=parameters,
            dependencies=dependencies or [],
        )

        self.executions[tool_id] = execution
        self.execution_queue.append(execution)
        self.dependency_graph.add_tool(tool_id)

        return execution

    def add_dependency(
        self,
        source_tool: str,
        target_tool: str,
        dep_type: DependencyType = DependencyType.SEQUENTIAL,
    ) -> None:
        """Add a dependency between tools."""
        dep = ExecutionDependency(
            source_tool=source_tool,
            target_tool=target_tool,
            dependency_type=dep_type,
        )
        self.dependency_graph.add_dependency(dep)

    async def execute(self) -> Dict[str, ToolExecution]:
        """
        Execute all queued tools respecting dependencies.

        Returns:
            Dict of tool_id -> ToolExecution with results
        """
        import time

        completed = {}
        running_tasks = {}

        while len(completed) < len(self.executions):
            # Find tools that are ready to execute
            ready = self.dependency_graph.get_ready_tools(completed)

            if not ready and not running_tasks:
                # No progress possible
                break

            # Start new tasks
            for tool_id in ready:
                if tool_id not in running_tasks and tool_id not in completed:
                    execution = self.executions[tool_id]
                    task = asyncio.create_task(
                        self._execute_tool(execution)
                    )
                    running_tasks[tool_id] = task

            # Wait for at least one task to complete
            if running_tasks:
                done, pending = await asyncio.wait(
                    running_tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Process completed tasks
                completed_tools = []
                for tool_id, task in list(running_tasks.items()):
                    if task in done:
                        try:
                            result = await task
                            completed[tool_id] = result
                            completed_tools.append(tool_id)
                        except Exception as e:
                            execution = self.executions[tool_id]
                            execution.status = "failed"
                            execution.error = str(e)
                            completed[tool_id] = execution
                            completed_tools.append(tool_id)

                # Remove completed from running
                for tool_id in completed_tools:
                    del running_tasks[tool_id]

        return completed

    async def _execute_tool(self, execution: ToolExecution) -> ToolExecution:
        """Execute a single tool."""
        import time

        execution.status = "running"
        execution.start_time = time.time()

        try:
            if execution.tool_name not in self.available_tools:
                raise ValueError(f"Tool '{execution.tool_name}' not available")

            tool = self.available_tools[execution.tool_name]

            # Call tool (async or sync)
            if inspect.iscoroutinefunction(tool):
                result = await tool(**execution.parameters)
            else:
                result = tool(**execution.parameters)

            execution.result = result
            execution.status = "completed"

        except Exception as e:
            execution.error = str(e)
            execution.status = "failed"

        finally:
            execution.end_time = time.time()

        return execution

    async def execute_parallel(self, max_concurrent: int = 5) -> Dict[str, ToolExecution]:
        """
        Execute tools with maximum concurrency limit.

        Args:
            max_concurrent: Maximum number of concurrent executions

        Returns:
            Dict of results
        """
        completed = {}
        running_tasks = {}
        processed = set()

        while len(completed) < len(self.executions):
            # Find ready tools
            ready = [
                t for t in self.dependency_graph.get_ready_tools(completed)
                if t not in processed
            ]

            # Start up to max_concurrent tasks
            can_start = max_concurrent - len(running_tasks)
            for tool_id in ready[:can_start]:
                if tool_id not in running_tasks:
                    execution = self.executions[tool_id]
                    task = asyncio.create_task(self._execute_tool(execution))
                    running_tasks[tool_id] = task
                    processed.add(tool_id)

            if not running_tasks:
                break

            # Wait for tasks
            done, pending = await asyncio.wait(
                running_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Collect results
            for tool_id in list(running_tasks.keys()):
                task = running_tasks[tool_id]
                if task in done:
                    result = await task
                    completed[tool_id] = result
                    del running_tasks[tool_id]

        return completed

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        completed = [e for e in self.executions.values() if e.status == "completed"]
        failed = [e for e in self.executions.values() if e.status == "failed"]
        total_duration = sum(e.duration() for e in completed)

        return {
            "total_tools": len(self.executions),
            "completed": len(completed),
            "failed": len(failed),
            "total_duration": total_duration,
            "average_duration": (
                total_duration / len(completed) if completed else 0
            ),
            "success_rate": (
                len(completed) / len(self.executions)
                if self.executions else 0
            ),
        }
