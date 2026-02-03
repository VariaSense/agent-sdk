"""Metrics and analytics for routing decisions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict


@dataclass
class RoutingMetrics:
    """Metrics for a routing decision."""
    decision_time_ms: float
    paths_evaluated: int
    conditions_checked: int
    confidence_score: float
    strategy_used: str
    total_tokens_estimated: int
    estimated_cost: float
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_time_ms": self.decision_time_ms,
            "paths_evaluated": self.paths_evaluated,
            "conditions_checked": self.conditions_checked,
            "confidence_score": self.confidence_score,
            "strategy_used": self.strategy_used,
            "total_tokens_estimated": self.total_tokens_estimated,
            "estimated_cost": self.estimated_cost,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class RoutingAnalytics:
    """Track and analyze routing decisions over time."""
    
    def __init__(self):
        """Initialize analytics tracker."""
        self.decisions: List[RoutingMetrics] = []
        self.path_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "success_count": 0,
            "total_cost": 0.0,
            "total_tokens": 0,
            "avg_confidence": 0.0,
            "avg_decision_time_ms": 0.0
        })
        self.strategy_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "success_count": 0,
            "avg_confidence": 0.0
        })
    
    def record_decision(
        self,
        path_id: str,
        metrics: RoutingMetrics
    ) -> None:
        """Record routing decision.
        
        Args:
            path_id: ID of selected path
            metrics: Routing metrics
        """
        self.decisions.append(metrics)
        
        # Update path statistics
        path_stat = self.path_stats[path_id]
        path_stat["count"] += 1
        if metrics.success:
            path_stat["success_count"] += 1
        path_stat["total_cost"] += metrics.estimated_cost
        path_stat["total_tokens"] += metrics.total_tokens_estimated
        
        # Update running averages
        total = path_stat["count"]
        path_stat["avg_confidence"] = (
            (path_stat["avg_confidence"] * (total - 1) + metrics.confidence_score) / total
        )
        path_stat["avg_decision_time_ms"] = (
            (path_stat["avg_decision_time_ms"] * (total - 1) + metrics.decision_time_ms) / total
        )
        
        # Update strategy statistics
        strategy = metrics.strategy_used
        strat_stat = self.strategy_stats[strategy]
        strat_stat["count"] += 1
        if metrics.success:
            strat_stat["success_count"] += 1
        total_strat = strat_stat["count"]
        strat_stat["avg_confidence"] = (
            (strat_stat["avg_confidence"] * (total_strat - 1) + metrics.confidence_score) / total_strat
        )
    
    def get_path_success_rates(self) -> Dict[str, float]:
        """Get success rate per path.
        
        Returns:
            Dict mapping path_id to success rate (0.0-1.0)
        """
        rates = {}
        for path_id, stats in self.path_stats.items():
            if stats["count"] > 0:
                rates[path_id] = stats["success_count"] / stats["count"]
            else:
                rates[path_id] = 0.0
        return rates
    
    def get_optimal_paths(
        self,
        context_type: str = None,
        top_n: int = 5
    ) -> List[str]:
        """Get best-performing paths.
        
        Args:
            context_type: Optional context type filter
            top_n: Number of top paths to return
        
        Returns:
            List of path IDs sorted by performance
        """
        # Sort by success rate then by count
        sorted_paths = sorted(
            self.path_stats.items(),
            key=lambda x: (
                x[1]["success_count"] / max(1, x[1]["count"]),
                x[1]["count"]
            ),
            reverse=True
        )
        
        return [path_id for path_id, _ in sorted_paths[:top_n]]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall routing statistics.
        
        Returns:
            Dict with aggregate statistics
        """
        if not self.decisions:
            return {
                "total_decisions": 0,
                "success_rate": 0.0,
                "avg_confidence": 0.0,
                "avg_decision_time_ms": 0.0,
                "total_cost": 0.0
            }
        
        total = len(self.decisions)
        successful = sum(1 for d in self.decisions if d.success)
        avg_confidence = sum(d.confidence_score for d in self.decisions) / total
        avg_time = sum(d.decision_time_ms for d in self.decisions) / total
        total_cost = sum(d.estimated_cost for d in self.decisions)
        
        return {
            "total_decisions": total,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_confidence": avg_confidence,
            "avg_decision_time_ms": avg_time,
            "total_cost": total_cost,
            "unique_paths": len(self.path_stats),
            "unique_strategies": len(self.strategy_stats)
        }
    
    def get_path_statistics(self, path_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for specific path.
        
        Args:
            path_id: ID of path
        
        Returns:
            Dict with path statistics or None if not found
        """
        if path_id not in self.path_stats:
            return None
        
        stats = self.path_stats[path_id]
        return {
            **stats,
            "success_rate": stats["success_count"] / max(1, stats["count"]),
            "avg_cost_per_decision": stats["total_cost"] / max(1, stats["count"])
        }
    
    def get_strategy_statistics(self, strategy: str) -> Optional[Dict[str, Any]]:
        """Get statistics for specific strategy.
        
        Args:
            strategy: Strategy name
        
        Returns:
            Dict with strategy statistics or None if not found
        """
        if strategy not in self.strategy_stats:
            return None
        
        stats = self.strategy_stats[strategy]
        return {
            **stats,
            "success_rate": stats["success_count"] / max(1, stats["count"])
        }
    
    def reset(self) -> None:
        """Reset all analytics data."""
        self.decisions.clear()
        self.path_stats.clear()
        self.strategy_stats.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analytics to dictionary.
        
        Returns:
            Dict representation of analytics
        """
        return {
            "total_decisions": len(self.decisions),
            "statistics": self.get_statistics(),
            "path_stats": dict(self.path_stats),
            "strategy_stats": dict(self.strategy_stats),
            "recent_decisions": [d.to_dict() for d in self.decisions[-10:]]
        }
