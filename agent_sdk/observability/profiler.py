"""
Performance profiling for Agent SDK.

Provides detailed performance analysis, bottleneck identification, and critical path analysis.

Features:
- Step-by-step timing
- Tool execution profiling
- Critical path analysis
- Bottleneck identification
- Memory usage tracking
- Performance comparisons
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json
import tracemalloc


@dataclass
class OperationTiming:
    """Timing information for a single operation."""
    operation_name: str
    start_time: float  # Time in seconds since epoch
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    parent_operation: Optional[str] = None
    depth: int = 0  # For nested operations
    status: str = "running"  # "running", "complete", "error"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self, end_time: Optional[float] = None) -> None:
        """Mark operation as complete."""
        self.end_time = end_time
        if end_time and self.start_time:
            self.duration_ms = (end_time - self.start_time) * 1000
        self.status = "complete"
    
    def mark_error(self, error: str) -> None:
        """Mark operation with error."""
        self.status = "error"
        self.error = error
        self.end_time = datetime.now().timestamp()
        if self.end_time and self.start_time:
            self.duration_ms = (self.end_time - self.start_time) * 1000
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "operation_name": self.operation_name,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "parent": self.parent_operation,
            "depth": self.depth,
            "metadata": self.metadata
        }


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    timestamp: datetime
    current_bytes: int
    peak_bytes: int
    allocated_blocks: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "current_mb": round(self.current_bytes / 1024 / 1024, 2),
            "peak_mb": round(self.peak_bytes / 1024 / 1024, 2),
            "allocated_blocks": self.allocated_blocks
        }


@dataclass
class CriticalPathAnalysis:
    """Analysis of the critical path."""
    total_duration_ms: float
    critical_path_duration_ms: float
    critical_path_operations: List[str]
    parallelization_factor: float  # How much could be parallelized
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "total_duration_ms": round(self.total_duration_ms, 2),
            "critical_path_duration_ms": round(self.critical_path_duration_ms, 2),
            "critical_path_operations": self.critical_path_operations,
            "parallelization_potential": round(self.parallelization_factor, 2)
        }


@dataclass
class BottleneckAnalysis:
    """Analysis of performance bottlenecks."""
    slowest_operation: str
    slowest_duration_ms: float
    slowest_percentage: float  # % of total time
    resource_bottleneck: Optional[str]  # e.g., "memory", "io", "cpu"
    recommendations: List[str]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "slowest_operation": self.slowest_operation,
            "slowest_duration_ms": round(self.slowest_duration_ms, 2),
            "slowest_percentage": round(self.slowest_percentage, 2),
            "resource_bottleneck": self.resource_bottleneck,
            "recommendations": self.recommendations
        }


class PerformanceProfiler:
    """Profiles performance of operations."""
    
    def __init__(self, enable_memory_tracking: bool = True):
        """
        Initialize performance profiler.
        
        Args:
            enable_memory_tracking: Whether to track memory usage
        """
        self.enable_memory_tracking = enable_memory_tracking
        self.operations: Dict[str, OperationTiming] = {}
        self.operation_stack: List[str] = []  # Stack of current operations
        self.memory_snapshots: List[MemorySnapshot] = []
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        
        if enable_memory_tracking:
            tracemalloc.start()
    
    def start_session(self) -> None:
        """Start a profiling session."""
        self._start_time = datetime.now().timestamp()
    
    def end_session(self) -> None:
        """End a profiling session."""
        self._end_time = datetime.now().timestamp()
    
    def start_operation(self, operation_name: str, metadata: Optional[Dict] = None) -> None:
        """
        Start profiling an operation.
        
        Args:
            operation_name: Name of operation
            metadata: Additional metadata
        """
        start_time = datetime.now().timestamp()
        parent = self.operation_stack[-1] if self.operation_stack else None
        depth = len(self.operation_stack)
        
        timing = OperationTiming(
            operation_name=operation_name,
            start_time=start_time,
            parent_operation=parent,
            depth=depth,
            metadata=metadata or {}
        )
        
        self.operations[operation_name] = timing
        self.operation_stack.append(operation_name)
        
        if self.enable_memory_tracking:
            self._record_memory_snapshot()
    
    def end_operation(self, operation_name: str) -> None:
        """
        End profiling an operation.
        
        Args:
            operation_name: Name of operation
        """
        if operation_name in self.operations:
            end_time = datetime.now().timestamp()
            self.operations[operation_name].complete(end_time)
        
        if self.operation_stack and self.operation_stack[-1] == operation_name:
            self.operation_stack.pop()
        
        if self.enable_memory_tracking:
            self._record_memory_snapshot()
    
    def mark_operation_error(self, operation_name: str, error: str) -> None:
        """Mark operation with error."""
        if operation_name in self.operations:
            self.operations[operation_name].mark_error(error)
        
        if self.operation_stack and self.operation_stack[-1] == operation_name:
            self.operation_stack.pop()
    
    def _record_memory_snapshot(self) -> None:
        """Record a memory snapshot."""
        if not self.enable_memory_tracking:
            return
        
        current, peak = tracemalloc.get_traced_memory()
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        mem_snapshot = MemorySnapshot(
            timestamp=datetime.now(),
            current_bytes=current,
            peak_bytes=peak,
            allocated_blocks=len(top_stats)
        )
        self.memory_snapshots.append(mem_snapshot)
    
    def get_operation_profile(self, operation_name: str) -> Optional[OperationTiming]:
        """Get profile for a specific operation."""
        return self.operations.get(operation_name)
    
    def get_all_profiles(self) -> Dict[str, OperationTiming]:
        """Get all operation profiles."""
        return self.operations
    
    def get_sorted_by_duration(self, limit: Optional[int] = None) -> List[Tuple[str, float]]:
        """Get operations sorted by duration."""
        ops = [
            (name, timing.duration_ms or 0)
            for name, timing in self.operations.items()
            if timing.duration_ms is not None
        ]
        ops.sort(key=lambda x: x[1], reverse=True)
        return ops[:limit] if limit else ops
    
    def get_critical_path(self) -> CriticalPathAnalysis:
        """Analyze the critical path."""
        if not self.operations:
            return CriticalPathAnalysis(0, 0, [], 0)
        
        # Calculate total duration
        start_times = [op.start_time for op in self.operations.values()]
        end_times = [op.end_time for op in self.operations.values() if op.end_time]
        
        if not start_times or not end_times:
            return CriticalPathAnalysis(0, 0, [], 0)
        
        total_start = min(start_times)
        total_end = max(end_times)
        total_duration_ms = (total_end - total_start) * 1000
        
        # Find critical path (operations with no parallel work)
        critical_path = []
        critical_duration = 0
        
        for name, timing in self.operations.items():
            if timing.depth == 0 and timing.duration_ms:
                critical_path.append(name)
                critical_duration += timing.duration_ms
        
        # Calculate parallelization factor
        sequential_duration = sum(
            timing.duration_ms or 0
            for timing in self.operations.values()
        )
        
        parallelization_factor = (
            sequential_duration / critical_duration
            if critical_duration > 0 else 0
        )
        
        return CriticalPathAnalysis(
            total_duration_ms=total_duration_ms,
            critical_path_duration_ms=critical_duration,
            critical_path_operations=critical_path,
            parallelization_factor=parallelization_factor
        )
    
    def get_bottleneck_analysis(self) -> BottleneckAnalysis:
        """Analyze performance bottlenecks."""
        if not self.operations:
            return BottleneckAnalysis("none", 0, 0, None, [])
        
        # Find slowest operation
        slowest_op = None
        slowest_duration = 0
        
        for name, timing in self.operations.items():
            if timing.duration_ms and timing.duration_ms > slowest_duration:
                slowest_op = name
                slowest_duration = timing.duration_ms
        
        if not slowest_op:
            return BottleneckAnalysis("none", 0, 0, None, [])
        
        # Calculate percentage
        total_duration = sum(
            timing.duration_ms or 0
            for timing in self.operations.values()
        )
        
        percentage = (slowest_duration / total_duration * 100) if total_duration > 0 else 0
        
        # Determine resource bottleneck
        resource_bottleneck = None
        if slowest_duration > 5000:  # > 5 seconds
            resource_bottleneck = "io_latency"
        elif percentage > 80:
            resource_bottleneck = "single_threaded"
        
        # Recommendations
        recommendations = []
        if percentage > 50:
            recommendations.append(f"Optimize {slowest_op} - it takes {percentage:.1f}% of total time")
        if resource_bottleneck == "io_latency":
            recommendations.append("Consider parallel I/O or batching requests")
        if resource_bottleneck == "single_threaded":
            recommendations.append("Consider parallelizing other operations")
        
        return BottleneckAnalysis(
            slowest_operation=slowest_op,
            slowest_duration_ms=slowest_duration,
            slowest_percentage=percentage,
            resource_bottleneck=resource_bottleneck,
            recommendations=recommendations
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get profiling summary."""
        if not self.operations:
            return {"message": "No operations profiled"}
        
        sorted_ops = self.get_sorted_by_duration()
        critical_path = self.get_critical_path()
        bottlenecks = self.get_bottleneck_analysis()
        
        return {
            "total_operations": len(self.operations),
            "total_duration_ms": critical_path.total_duration_ms,
            "slowest_operations": sorted_ops[:5],
            "critical_path": critical_path.to_dict(),
            "bottlenecks": bottlenecks.to_dict(),
            "memory_usage": {
                "snapshots": len(self.memory_snapshots),
                "latest": self.memory_snapshots[-1].to_dict() if self.memory_snapshots else None
            }
        }
    
    def export_to_json(self, filepath: str) -> None:
        """Export profile to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "operations": {
                name: timing.to_dict()
                for name, timing in self.operations.items()
            },
            "analysis": {
                "critical_path": self.get_critical_path().to_dict(),
                "bottlenecks": self.get_bottleneck_analysis().to_dict(),
                "summary": self.get_summary()
            },
            "memory": [snap.to_dict() for snap in self.memory_snapshots]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def clear(self) -> None:
        """Clear profiling data."""
        self.operations.clear()
        self.operation_stack.clear()
        self.memory_snapshots.clear()
        self._start_time = None
        self._end_time = None


def create_profiler(enable_memory_tracking: bool = True) -> PerformanceProfiler:
    """
    Create a performance profiler.
    
    Args:
        enable_memory_tracking: Whether to track memory usage
        
    Returns:
        PerformanceProfiler instance
    """
    return PerformanceProfiler(enable_memory_tracking)
