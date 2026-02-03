"""Tests for Parallel Tool Execution."""
import pytest
import asyncio
from agent_sdk.execution.parallel_executor import (
    ToolExecution, DependencyGraph, ParallelToolExecutor,
    ExecutionDependency, DependencyType,
)


@pytest.fixture
def sample_tools():
    return {
        "add": lambda a, b: a + b,
        "multiply": lambda a, b: a * b,
        "divide": lambda a, b: a / b if b != 0 else None,
    }


class TestToolExecution:
    def test_create_execution(self):
        exec = ToolExecution(
            tool_id="t1",
            tool_name="search",
            parameters={"query": "test"},
        )
        assert exec.tool_id == "t1"
        assert exec.status == "pending"

    def test_execution_dict(self):
        exec = ToolExecution("t1", "search", {})
        d = exec.to_dict()
        assert d["status"] == "pending"
        assert d["tool_id"] == "t1"


class TestDependencyGraph:
    def test_graph_creation(self):
        graph = DependencyGraph()
        graph.add_tool("t1")
        assert "t1" in graph.tools

    def test_add_dependency(self):
        graph = DependencyGraph()
        graph.add_tool("t1")
        graph.add_tool("t2")
        dep = ExecutionDependency("t1", "t2", DependencyType.SEQUENTIAL)
        graph.add_dependency(dep)
        assert len(graph.dependencies["t2"]) == 1

    def test_get_ready_tools(self):
        graph = DependencyGraph()
        graph.add_tool("t1")
        graph.add_tool("t2")
        dep = ExecutionDependency("t1", "t2")
        graph.add_dependency(dep)

        # No dependencies completed
        ready = graph.get_ready_tools({})
        assert "t1" in ready

    def test_get_all_dependencies(self):
        graph = DependencyGraph()
        for i in range(3):
            graph.add_tool(f"t{i}")
        graph.add_dependency(ExecutionDependency("t0", "t1"))
        graph.add_dependency(ExecutionDependency("t1", "t2"))

        deps = graph.get_all_dependencies("t2")
        assert "t0" in deps
        assert "t1" in deps


class TestParallelToolExecutor:
    def test_executor_creation(self, sample_tools):
        executor = ParallelToolExecutor(sample_tools)
        assert len(executor.available_tools) == 3

    def test_add_execution(self, sample_tools):
        executor = ParallelToolExecutor(sample_tools)
        exec = executor.add_tool_execution(
            "t1",
            "add",
            {"a": 1, "b": 2},
        )
        assert exec.tool_name == "add"

    @pytest.mark.asyncio
    async def test_execute_simple(self, sample_tools):
        executor = ParallelToolExecutor(sample_tools)
        executor.add_tool_execution("t1", "add", {"a": 2, "b": 3})

        results = await executor.execute()
        assert "t1" in results
        assert results["t1"].status == "completed"
        assert results["t1"].result == 5

    @pytest.mark.asyncio
    async def test_execute_with_dependency(self, sample_tools):
        executor = ParallelToolExecutor(sample_tools)
        executor.add_tool_execution("t1", "add", {"a": 2, "b": 3})
        executor.add_tool_execution("t2", "multiply", {"a": 1, "b": 2})
        executor.add_dependency("t1", "t2")

        results = await executor.execute()
        assert len(results) == 2
        assert results["t1"].status == "completed"
        assert results["t2"].status == "completed"

    @pytest.mark.asyncio
    async def test_execute_parallel(self, sample_tools):
        executor = ParallelToolExecutor(sample_tools)
        executor.add_tool_execution("t1", "add", {"a": 1, "b": 2})
        executor.add_tool_execution("t2", "multiply", {"a": 2, "b": 3})

        results = await executor.execute_parallel(max_concurrent=2)
        assert len(results) == 2

    def test_execution_stats(self, sample_tools):
        executor = ParallelToolExecutor(sample_tools)
        executor.add_tool_execution("t1", "add", {"a": 1, "b": 1})
        stats = executor.get_execution_stats()
        assert "total_tools" in stats
        assert stats["total_tools"] == 1
