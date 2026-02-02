"""Tests for parallel tool execution."""

import pytest
from agent_sdk.execution.parallel import (
    TaskStatus,
    TaskPriority,
    Task,
    TaskResult,
    TaskScheduler,
    AsyncTaskScheduler,
    create_task_scheduler,
)


class TestTaskResult:
    """Test TaskResult functionality."""

    def test_create_result(self):
        """Test creating task result."""
        result = TaskResult(task_id="task1", status=TaskStatus.COMPLETED, result="value")
        assert result.task_id == "task1"
        assert result.status == TaskStatus.COMPLETED
        assert result.result == "value"

    def test_result_to_dict(self):
        """Test converting result to dict."""
        result = TaskResult(
            task_id="task1", status=TaskStatus.COMPLETED, result="value"
        )
        result_dict = result.to_dict()
        assert result_dict["task_id"] == "task1"
        assert result_dict["status"] == "completed"


class TestTask:
    """Test Task functionality."""

    def test_create_task(self):
        """Test creating a task."""
        task = Task(
            task_id="task1",
            tool_name="calculator",
            params={"expr": "2+2"},
            priority=TaskPriority.NORMAL,
        )
        assert task.task_id == "task1"
        assert task.tool_name == "calculator"
        assert task.params == {"expr": "2+2"}

    def test_task_with_dependencies(self):
        """Test task with dependencies."""
        task = Task(
            task_id="task2",
            tool_name="summarize",
            params={},
            dependencies=["task1"],
        )
        assert "task1" in task.dependencies

    def test_task_to_dict(self):
        """Test converting task to dict."""
        task = Task(
            task_id="task1",
            tool_name="tool1",
            params={"key": "value"},
            priority=TaskPriority.HIGH,
        )
        task_dict = task.to_dict()
        assert task_dict["task_id"] == "task1"
        assert task_dict["tool_name"] == "tool1"
        assert task_dict["priority"] == "high"


class TestTaskScheduler:
    """Test TaskScheduler functionality."""

    def test_create_scheduler(self):
        """Test creating scheduler."""
        scheduler = TaskScheduler(max_workers=4)
        assert scheduler.max_workers == 4

    def test_add_task(self):
        """Test adding tasks."""
        scheduler = TaskScheduler()
        task = scheduler.add_task(
            "task1", "tool1", {"key": "value"}, TaskPriority.NORMAL
        )
        assert "task1" in scheduler.tasks

    def test_task_dependency_check(self):
        """Test dependency checking."""
        scheduler = TaskScheduler()
        scheduler.add_task("task1", "tool1", {})
        scheduler.add_task("task2", "tool2", {}, dependencies=["task1"])

        # Manually complete task1
        result = TaskResult(task_id="task1", status=TaskStatus.COMPLETED)
        scheduler.completed_tasks["task1"] = result

        ready_tasks = scheduler._get_ready_tasks()
        assert any(t.task_id == "task2" for t in ready_tasks)

    def test_execute_tasks_simple(self):
        """Test executing simple tasks."""

        def tool1(**kwargs):
            return "result1"

        def tool2(**kwargs):
            return "result2"

        scheduler = TaskScheduler()
        scheduler.add_task("task1", "tool1", {})
        scheduler.add_task("task2", "tool2", {})

        results = scheduler.execute_tasks({"tool1": tool1, "tool2": tool2})
        assert len(results) == 2
        assert results["task1"].status == TaskStatus.COMPLETED
        assert results["task2"].status == TaskStatus.COMPLETED

    def test_execute_tasks_with_dependencies(self):
        """Test executing tasks with dependencies."""

        def tool1(**kwargs):
            return "result1"

        def tool2(**kwargs):
            return "result2"

        scheduler = TaskScheduler()
        scheduler.add_task("task1", "tool1", {})
        scheduler.add_task("task2", "tool2", {}, dependencies=["task1"])

        results = scheduler.execute_tasks({"tool1": tool1, "tool2": tool2})
        assert results["task1"].status == TaskStatus.COMPLETED
        assert results["task2"].status == TaskStatus.COMPLETED

    def test_execute_tasks_tool_not_found(self):
        """Test handling missing tool."""
        scheduler = TaskScheduler()
        scheduler.add_task("task1", "unknown_tool", {})

        results = scheduler.execute_tasks({})
        assert results["task1"].status == TaskStatus.FAILED
        assert "not found" in results["task1"].error

    def test_task_priority_ordering(self):
        """Test task priority ordering."""
        scheduler = TaskScheduler()
        scheduler.add_task("task1", "tool1", {}, TaskPriority.LOW)
        scheduler.add_task("task2", "tool2", {}, TaskPriority.CRITICAL)
        scheduler.add_task("task3", "tool3", {}, TaskPriority.NORMAL)

        ready = scheduler._get_ready_tasks()
        assert ready[0].task_id == "task2"  # CRITICAL first
        assert ready[1].task_id == "task3"  # NORMAL second
        assert ready[2].task_id == "task1"  # LOW last

    def test_get_statistics(self):
        """Test getting execution statistics."""

        def tool1(**kwargs):
            return "result"

        scheduler = TaskScheduler()
        scheduler.add_task("task1", "tool1", {})
        scheduler.add_task("task2", "tool1", {})

        results = scheduler.execute_tasks({"tool1": tool1})
        stats = scheduler.get_statistics()

        assert stats["total_tasks"] == 2
        assert stats["completed"] == 2
        assert stats["success_rate"] == 100.0

    def test_execution_plan(self):
        """Test getting execution plan."""
        scheduler = TaskScheduler()
        scheduler.add_task("task1", "tool1", {})
        scheduler.add_task("task2", "tool2", {})

        plan = scheduler.get_execution_plan()
        assert plan["total_tasks"] == 2
        assert len(plan["tasks"]) == 2


class TestAsyncTaskScheduler:
    """Test AsyncTaskScheduler functionality."""

    def test_create_async_scheduler(self):
        """Test creating async scheduler."""
        scheduler = AsyncTaskScheduler(max_concurrent=5)
        assert scheduler.max_concurrent == 5

    def test_add_task_async(self):
        """Test adding tasks to async scheduler."""
        scheduler = AsyncTaskScheduler()
        task = scheduler.add_task(
            "task1", "tool1", {"param": "value"}, TaskPriority.HIGH
        )
        assert task.task_id == "task1"

    @pytest.mark.asyncio
    async def test_execute_tasks_async(self):
        """Test executing async tasks."""

        def sync_tool(**kwargs):
            return "sync_result"

        async def async_tool(**kwargs):
            return "async_result"

        scheduler = AsyncTaskScheduler()
        scheduler.add_task("task1", "sync_tool", {})
        scheduler.add_task("task2", "async_tool", {})

        results = await scheduler.execute_tasks(
            {"sync_tool": sync_tool, "async_tool": async_tool}
        )

        assert len(results) == 2
        assert results["task1"].status == TaskStatus.COMPLETED
        assert results["task2"].status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_async_with_dependencies(self):
        """Test async execution with dependencies."""

        def tool1(**kwargs):
            return "result1"

        def tool2(**kwargs):
            return "result2"

        scheduler = AsyncTaskScheduler()
        scheduler.add_task("task1", "tool1", {})
        scheduler.add_task("task2", "tool2", {}, dependencies=["task1"])

        results = await scheduler.execute_tasks(
            {"tool1": tool1, "tool2": tool2}
        )

        assert results["task1"].status == TaskStatus.COMPLETED
        assert results["task2"].status == TaskStatus.COMPLETED


class TestCreateTaskScheduler:
    """Test factory function."""

    def test_create_sync_scheduler(self):
        """Test creating sync scheduler."""
        scheduler = create_task_scheduler(async_mode=False, max_workers=4)
        assert isinstance(scheduler, TaskScheduler)

    def test_create_async_scheduler(self):
        """Test creating async scheduler."""
        scheduler = create_task_scheduler(async_mode=True, max_workers=4)
        assert isinstance(scheduler, AsyncTaskScheduler)


class TestParallelExecution:
    """Integration tests for parallel execution."""

    def test_parallel_tool_calls(self):
        """Test parallel execution of tools."""
        call_count = {"count": 0}

        def slow_tool(duration=10):
            call_count["count"] += 1
            return f"result_{call_count['count']}"

        scheduler = TaskScheduler(max_workers=2)
        scheduler.add_task("task1", "tool", {"duration": 1})
        scheduler.add_task("task2", "tool", {"duration": 1})
        scheduler.add_task("task3", "tool", {"duration": 1})

        results = scheduler.execute_tasks({"tool": slow_tool})
        assert len(results) == 3
        assert all(r.status == TaskStatus.COMPLETED for r in results.values())

    def test_dependency_chain(self):
        """Test chain of dependencies."""

        def process(**kwargs):
            return f"processed_{kwargs.get('value', 'none')}"

        scheduler = TaskScheduler()
        scheduler.add_task("task1", "process", {"value": "A"})
        scheduler.add_task("task2", "process", {"value": "B"}, dependencies=["task1"])
        scheduler.add_task(
            "task3", "process", {"value": "C"}, dependencies=["task2"]
        )

        results = scheduler.execute_tasks({"process": process})
        assert all(r.status == TaskStatus.COMPLETED for r in results.values())
        assert results["task1"].end_time <= results["task2"].start_time
        assert results["task2"].end_time <= results["task3"].start_time
