"""
Parallel Tool Execution Engine

Implements concurrent tool execution with:
- Parallel tool invocation
- Dependency resolution
- Task batching and scheduling
- Concurrent execution with proper error handling
- Performance metrics and monitoring

Enables agents to call multiple tools simultaneously for better performance.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Coroutine
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed


logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Task execution priority."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class TaskResult:
    """Result of a task execution."""

    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
        }


@dataclass
class Task:
    """
    A task to be executed in parallel.

    Attributes:
        task_id: Unique task identifier
        tool_name: Name of the tool to invoke
        params: Parameters for the tool
        priority: Execution priority
        dependencies: Task IDs this task depends on
        result: Result of execution (after completion)
    """

    task_id: str
    tool_name: str
    params: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    dependencies: List[str] = field(default_factory=list)
    result: Optional[TaskResult] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "tool_name": self.tool_name,
            "params": self.params,
            "priority": self.priority.value,
            "dependencies": self.dependencies,
            "status": self.result.status.value if self.result else "pending",
            "result": self.result.to_dict() if self.result else None,
        }


class TaskScheduler:
    """
    Schedules and executes tasks with dependency resolution.

    Manages task ordering, parallelization, and execution.
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize task scheduler.

        Args:
            max_workers: Maximum number of concurrent workers
        """
        self.max_workers = max_workers
        self.tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def add_task(
        self,
        task_id: str,
        tool_name: str,
        params: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: Optional[List[str]] = None,
    ) -> Task:
        """
        Add a task to the schedule.

        Args:
            task_id: Unique task ID
            tool_name: Name of tool to invoke
            params: Tool parameters
            priority: Task priority
            dependencies: Task IDs this depends on

        Returns:
            Created Task
        """
        task = Task(
            task_id=task_id,
            tool_name=tool_name,
            params=params,
            priority=priority,
            dependencies=dependencies or [],
        )
        self.tasks[task_id] = task
        logger.debug(f"Added task: {task_id} ({tool_name})")
        return task

    def _get_dependencies_met(self, task: Task) -> bool:
        """Check if all task dependencies are completed."""
        for dep_id in task.dependencies:
            if dep_id not in self.completed_tasks:
                return False
        return True

    def _get_ready_tasks(self) -> List[Task]:
        """Get tasks ready for execution."""
        ready = []
        for task in self.tasks.values():
            if self.completed_tasks.get(task.task_id) is None:
                if self._get_dependencies_met(task):
                    ready.append(task)

        # Sort by priority
        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.NORMAL: 2,
            TaskPriority.LOW: 3,
        }
        ready.sort(key=lambda t: priority_order.get(t.priority, 2))
        return ready

    def execute_tasks(
        self, tool_registry: Dict[str, Callable]
    ) -> Dict[str, TaskResult]:
        """
        Execute all tasks with dependency management.

        Args:
            tool_registry: Dictionary mapping tool names to callables

        Returns:
            Dictionary of task results
        """
        results = {}

        while len(results) < len(self.tasks):
            ready_tasks = self._get_ready_tasks()

            if not ready_tasks:
                if len(results) < len(self.tasks):
                    logger.error("Circular dependency detected in tasks")
                    break
                break

            # Submit ready tasks
            futures = {}
            for task in ready_tasks:
                if task.tool_name not in tool_registry:
                    result = TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.FAILED,
                        error=f"Tool not found: {task.tool_name}",
                    )
                    results[task.task_id] = result
                    self.completed_tasks[task.task_id] = result
                    task.result = result
                else:
                    tool_func = tool_registry[task.tool_name]
                    future = self.executor.submit(
                        self._execute_task, task, tool_func
                    )
                    futures[future] = task

            # Wait for completion
            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result()
                    results[task.task_id] = result
                    self.completed_tasks[task.task_id] = result
                    task.result = result
                except Exception as e:
                    result = TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.FAILED,
                        error=str(e),
                    )
                    results[task.task_id] = result
                    self.completed_tasks[task.task_id] = result
                    task.result = result

        return results

    @staticmethod
    def _execute_task(task: Task, tool_func: Callable) -> TaskResult:
        """Execute a single task."""
        start_time = datetime.now()
        try:
            logger.debug(f"Executing task: {task.task_id}")
            result_value = tool_func(**task.params)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() * 1000
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result_value,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration,
            )
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() * 1000
            logger.error(f"Task failed: {task.task_id}: {str(e)}")
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration,
            )

    def get_execution_plan(self) -> Dict[str, Any]:
        """Get the execution plan showing task dependencies."""
        return {
            "total_tasks": len(self.tasks),
            "completed_tasks": len(self.completed_tasks),
            "tasks": [t.to_dict() for t in self.tasks.values()],
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics."""
        if not self.completed_tasks:
            return {
                "total_tasks": len(self.tasks),
                "completed": 0,
                "failed": 0,
                "total_duration_ms": 0,
            }

        total_duration = sum(
            r.duration_ms for r in self.completed_tasks.values()
        )
        failed = sum(
            1
            for r in self.completed_tasks.values()
            if r.status == TaskStatus.FAILED
        )

        return {
            "total_tasks": len(self.tasks),
            "completed": len(self.completed_tasks),
            "failed": failed,
            "success_rate": (
                (len(self.completed_tasks) - failed) / len(self.completed_tasks)
                * 100
            ),
            "total_duration_ms": total_duration,
            "avg_task_duration_ms": total_duration / len(self.completed_tasks),
        }

    def shutdown(self) -> None:
        """Shutdown the executor."""
        self.executor.shutdown(wait=True)


class AsyncTaskScheduler:
    """
    Async version of task scheduler using asyncio.

    Better for I/O-bound operations and coroutines.
    """

    def __init__(self, max_concurrent: int = 10):
        """
        Initialize async scheduler.

        Args:
            max_concurrent: Maximum concurrent coroutines
        """
        self.max_concurrent = max_concurrent
        self.tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        self.semaphore: Optional[asyncio.Semaphore] = None

    def add_task(
        self,
        task_id: str,
        tool_name: str,
        params: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        dependencies: Optional[List[str]] = None,
    ) -> Task:
        """Add a task."""
        task = Task(
            task_id=task_id,
            tool_name=tool_name,
            params=params,
            priority=priority,
            dependencies=dependencies or [],
        )
        self.tasks[task_id] = task
        return task

    async def execute_tasks(
        self, tool_registry: Dict[str, Callable]
    ) -> Dict[str, TaskResult]:
        """
        Execute all tasks asynchronously.

        Args:
            tool_registry: Dictionary of tools (can be async callables)

        Returns:
            Task results
        """
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        results = {}

        async def execute_with_deps(task: Task) -> TaskResult:
            # Wait for dependencies
            for dep_id in task.dependencies:
                while dep_id not in self.completed_tasks:
                    await asyncio.sleep(0.01)

            # Execute
            if task.tool_name not in tool_registry:
                return TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    error=f"Tool not found: {task.tool_name}",
                )

            async with self.semaphore:
                tool_func = tool_registry[task.tool_name]
                start_time = datetime.now()
                try:
                    if asyncio.iscoroutinefunction(tool_func):
                        result_value = await tool_func(**task.params)
                    else:
                        result_value = tool_func(**task.params)

                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds() * 1000
                    return TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.COMPLETED,
                        result=result_value,
                        start_time=start_time,
                        end_time=end_time,
                        duration_ms=duration,
                    )
                except Exception as e:
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds() * 1000
                    return TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.FAILED,
                        error=str(e),
                        start_time=start_time,
                        end_time=end_time,
                        duration_ms=duration,
                    )

        # Execute all tasks concurrently
        coros = [execute_with_deps(task) for task in self.tasks.values()]
        task_results = await asyncio.gather(*coros)

        for result in task_results:
            results[result.task_id] = result
            self.completed_tasks[result.task_id] = result
            for task in self.tasks.values():
                if task.task_id == result.task_id:
                    task.result = result

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics."""
        if not self.completed_tasks:
            return {
                "total_tasks": len(self.tasks),
                "completed": 0,
                "failed": 0,
            }

        failed = sum(
            1
            for r in self.completed_tasks.values()
            if r.status == TaskStatus.FAILED
        )

        return {
            "total_tasks": len(self.tasks),
            "completed": len(self.completed_tasks),
            "failed": failed,
            "success_rate": (
                (len(self.completed_tasks) - failed) / len(self.completed_tasks)
                * 100
                if self.completed_tasks
                else 0
            ),
        }


def create_task_scheduler(
    async_mode: bool = False, max_workers: int = 4
) -> Any:
    """
    Factory function to create task scheduler.

    Args:
        async_mode: Use async scheduler if True
        max_workers: Number of workers (ignored for async)

    Returns:
        TaskScheduler or AsyncTaskScheduler
    """
    if async_mode:
        return AsyncTaskScheduler(max_concurrent=max_workers)
    return TaskScheduler(max_workers=max_workers)


__all__ = [
    "TaskStatus",
    "TaskPriority",
    "Task",
    "TaskResult",
    "TaskScheduler",
    "AsyncTaskScheduler",
    "create_task_scheduler",
]
