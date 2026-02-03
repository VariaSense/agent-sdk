"""
Tests for performance profiling module.
"""

import pytest
import time
from datetime import datetime
from agent_sdk.observability.profiler import (
    PerformanceProfiler,
    OperationTiming,
    create_profiler
)


class TestOperationTiming:
    """Test OperationTiming class."""
    
    def test_create_operation_timing(self):
        """Test creating operation timing."""
        start = datetime.now().timestamp()
        timing = OperationTiming(
            operation_name="search",
            start_time=start
        )
        assert timing.operation_name == "search"
        assert timing.status == "running"
    
    def test_complete_operation(self):
        """Test completing operation."""
        start = datetime.now().timestamp()
        timing = OperationTiming(
            operation_name="search",
            start_time=start
        )
        
        end = start + 0.1  # 100ms later
        timing.complete(end)
        
        assert timing.status == "complete"
        assert timing.duration_ms == pytest.approx(100.0, abs=1.0)
    
    def test_mark_operation_error(self):
        """Test marking operation with error."""
        start = datetime.now().timestamp()
        timing = OperationTiming(
            operation_name="search",
            start_time=start
        )
        
        timing.mark_error("Connection timeout")
        
        assert timing.status == "error"
        assert timing.error == "Connection timeout"
    
    def test_operation_with_metadata(self):
        """Test operation with metadata."""
        timing = OperationTiming(
            operation_name="search",
            start_time=datetime.now().timestamp(),
            metadata={"query": "AI", "result_count": 42}
        )
        
        assert timing.metadata["query"] == "AI"
        assert timing.metadata["result_count"] == 42


class TestPerformanceProfiler:
    """Test PerformanceProfiler class."""
    
    def test_create_profiler(self):
        """Test creating profiler."""
        profiler = PerformanceProfiler()
        assert len(profiler.operations) == 0
    
    def test_start_operation(self):
        """Test starting operation."""
        profiler = PerformanceProfiler()
        profiler.start_operation("search")
        
        assert "search" in profiler.operations
        assert profiler.operations["search"].status == "running"
    
    def test_start_and_end_operation(self):
        """Test starting and ending operation."""
        profiler = PerformanceProfiler()
        profiler.start_operation("search")
        time.sleep(0.05)  # 50ms
        profiler.end_operation("search")
        
        timing = profiler.operations["search"]
        assert timing.status == "complete"
        assert timing.duration_ms >= 50
    
    def test_nested_operations(self):
        """Test nested operations."""
        profiler = PerformanceProfiler()
        
        profiler.start_operation("agent_run")
        profiler.start_operation("tool_call")
        profiler.end_operation("tool_call")
        profiler.end_operation("agent_run")
        
        tool_timing = profiler.operations["tool_call"]
        agent_timing = profiler.operations["agent_run"]
        
        assert tool_timing.parent_operation == "agent_run"
        assert tool_timing.depth == 1
        assert agent_timing.depth == 0
    
    def test_mark_operation_error(self):
        """Test marking operation with error."""
        profiler = PerformanceProfiler()
        profiler.start_operation("api_call")
        profiler.mark_operation_error("api_call", "Timeout")
        
        timing = profiler.operations["api_call"]
        assert timing.status == "error"
        assert timing.error == "Timeout"
    
    def test_get_operation_profile(self):
        """Test getting operation profile."""
        profiler = PerformanceProfiler()
        profiler.start_operation("search")
        profiler.end_operation("search")
        
        profile = profiler.get_operation_profile("search")
        assert profile is not None
        assert profile.operation_name == "search"
    
    def test_get_sorted_by_duration(self):
        """Test getting operations sorted by duration."""
        profiler = PerformanceProfiler()
        
        # Create operations with different durations
        for i, duration in enumerate([100, 50, 200, 75]):
            profiler.start_operation(f"op-{i}")
            time.sleep(duration / 1000)  # Convert to seconds
            profiler.end_operation(f"op-{i}")
        
        sorted_ops = profiler.get_sorted_by_duration()
        assert sorted_ops[0][0] == "op-2"  # 200ms should be first
        assert sorted_ops[-1][0] == "op-1"  # 50ms should be last
    
    def test_get_sorted_with_limit(self):
        """Test getting sorted operations with limit."""
        profiler = PerformanceProfiler()
        
        for i in range(5):
            profiler.start_operation(f"op-{i}")
            profiler.end_operation(f"op-{i}")
        
        sorted_ops = profiler.get_sorted_by_duration(limit=3)
        assert len(sorted_ops) == 3
    
    def test_critical_path_analysis(self):
        """Test critical path analysis."""
        profiler = PerformanceProfiler()
        
        # Simulate sequential operations
        profiler.start_operation("parent")
        for i in range(3):
            profiler.start_operation(f"child-{i}")
            time.sleep(0.01)
            profiler.end_operation(f"child-{i}")
        profiler.end_operation("parent")
        
        analysis = profiler.get_critical_path()
        assert analysis.total_duration_ms > 0
        assert analysis.critical_path_duration_ms > 0
    
    def test_bottleneck_analysis(self):
        """Test bottleneck analysis."""
        profiler = PerformanceProfiler()
        
        # Create operations where one is much slower
        profiler.start_operation("fast")
        time.sleep(0.01)
        profiler.end_operation("fast")
        
        profiler.start_operation("slow")
        time.sleep(0.05)
        profiler.end_operation("slow")
        
        analysis = profiler.get_bottleneck_analysis()
        assert analysis.slowest_operation == "slow"
        assert analysis.slowest_duration_ms > 40  # Should be ~50ms
        assert analysis.slowest_percentage > 50  # Should be >80%
    
    def test_get_summary(self):
        """Test getting profiling summary."""
        profiler = PerformanceProfiler()
        
        profiler.start_operation("op1")
        profiler.end_operation("op1")
        
        summary = profiler.get_summary()
        assert "total_operations" in summary
        assert summary["total_operations"] == 1
    
    def test_clear_profiler(self):
        """Test clearing profiler."""
        profiler = PerformanceProfiler()
        
        profiler.start_operation("op1")
        profiler.end_operation("op1")
        
        assert len(profiler.operations) == 1
        profiler.clear()
        assert len(profiler.operations) == 0


class TestCreateProfiler:
    """Test profiler factory function."""
    
    def test_create_profiler_with_memory_tracking(self):
        """Test creating profiler with memory tracking."""
        profiler = create_profiler(enable_memory_tracking=True)
        assert profiler.enable_memory_tracking is True
    
    def test_create_profiler_without_memory_tracking(self):
        """Test creating profiler without memory tracking."""
        profiler = create_profiler(enable_memory_tracking=False)
        assert profiler.enable_memory_tracking is False


class TestProfilerIntegration:
    """Integration tests for profiler."""
    
    def test_profile_agent_execution(self):
        """Test profiling agent execution."""
        profiler = create_profiler()
        profiler.start_session()
        
        # Simulate agent execution
        profiler.start_operation("agent_run")
        
        # Planning phase
        profiler.start_operation("planning")
        time.sleep(0.02)
        profiler.end_operation("planning")
        
        # Execution phase
        profiler.start_operation("execution")
        profiler.start_operation("tool_call_1")
        time.sleep(0.01)
        profiler.end_operation("tool_call_1")
        
        profiler.start_operation("tool_call_2")
        time.sleep(0.01)
        profiler.end_operation("tool_call_2")
        profiler.end_operation("execution")
        
        profiler.end_operation("agent_run")
        profiler.end_session()
        
        # Verify
        summary = profiler.get_summary()
        assert summary["total_operations"] > 0
        
        agent_timing = profiler.get_operation_profile("agent_run")
        assert agent_timing.duration_ms >= 40  # At least 40ms
    
    def test_profile_with_error_handling(self):
        """Test profiling with error handling."""
        profiler = create_profiler()
        
        profiler.start_operation("api_call")
        time.sleep(0.01)
        profiler.mark_operation_error("api_call", "Network error")
        
        timing = profiler.get_operation_profile("api_call")
        assert timing.status == "error"
        assert timing.error == "Network error"
        
        summary = profiler.get_summary()
        analysis = profiler.get_bottleneck_analysis()
        assert analysis.slowest_operation == "api_call"
    
    def test_deeply_nested_operations(self):
        """Test profiling deeply nested operations."""
        profiler = create_profiler()
        
        profiler.start_operation("level1")
        profiler.start_operation("level2")
        profiler.start_operation("level3")
        profiler.start_operation("level4")
        time.sleep(0.01)
        profiler.end_operation("level4")
        profiler.end_operation("level3")
        profiler.end_operation("level2")
        profiler.end_operation("level1")
        
        level4 = profiler.get_operation_profile("level4")
        assert level4.depth == 3
        assert level4.parent_operation == "level3"
        
        level1 = profiler.get_operation_profile("level1")
        assert level1.depth == 0
