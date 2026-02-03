"""
Cost Tracking for Agent SDK

Provides cost tracking and analysis for agent operations.
Supports multiple pricing models and cost aggregation.

Features:
- Per-model token pricing configuration
- Token cost calculation
- Aggregated cost reports
- Cost per agent/conversation
- Budget tracking and alerts
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import json
from datetime import datetime


class CostUnit(Enum):
    """Units for cost measurement."""
    TOKENS = "tokens"
    CHARACTERS = "characters"
    REQUESTS = "requests"
    TIME = "time"  # Per hour or per minute


@dataclass
class ModelPricing:
    """Pricing configuration for a specific model."""
    model_id: str
    input_price_per_1k: float  # Price per 1K tokens for input
    output_price_per_1k: float  # Price per 1K tokens for output
    name: str = ""
    provider: str = ""  # e.g., "openai", "anthropic"
    
    def calculate_input_cost(self, input_tokens: int) -> float:
        """Calculate cost for input tokens."""
        return (input_tokens / 1000) * self.input_price_per_1k
    
    def calculate_output_cost(self, output_tokens: int) -> float:
        """Calculate cost for output tokens."""
        return (output_tokens / 1000) * self.output_price_per_1k
    
    def calculate_total_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate total cost for input and output tokens."""
        return self.calculate_input_cost(input_tokens) + self.calculate_output_cost(output_tokens)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "provider": self.provider,
            "input_price_per_1k": self.input_price_per_1k,
            "output_price_per_1k": self.output_price_per_1k
        }


@dataclass
class TokenUsage:
    """Token usage for a single operation."""
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return self.input_tokens + self.output_tokens
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens
        }


@dataclass
class OperationCost:
    """Cost information for a single operation."""
    operation_id: str
    operation_name: str
    model_id: str
    token_usage: TokenUsage
    cost: float
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "operation_id": self.operation_id,
            "operation_name": self.operation_name,
            "model_id": self.model_id,
            "token_usage": self.token_usage.to_dict(),
            "cost": self.cost,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class CostSummary:
    """Summary of costs for a period or agent."""
    agent_id: str
    period_start: datetime
    period_end: datetime
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    operation_count: int = 0
    cost_by_model: Dict[str, float] = field(default_factory=dict)
    cost_by_operation: Dict[str, float] = field(default_factory=dict)
    
    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return self.total_input_tokens + self.total_output_tokens
    
    @property
    def average_cost_per_operation(self) -> float:
        """Get average cost per operation."""
        if self.operation_count == 0:
            return 0.0
        return self.total_cost / self.operation_count
    
    @property
    def average_tokens_per_operation(self) -> float:
        """Get average tokens per operation."""
        if self.operation_count == 0:
            return 0.0
        return self.total_tokens / self.operation_count
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_cost": round(self.total_cost, 6),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "operation_count": self.operation_count,
            "average_cost_per_operation": round(self.average_cost_per_operation, 6),
            "average_tokens_per_operation": round(self.average_tokens_per_operation, 2),
            "cost_by_model": {k: round(v, 6) for k, v in self.cost_by_model.items()},
            "cost_by_operation": {k: round(v, 6) for k, v in self.cost_by_operation.items()}
        }


class CostTracker:
    """
    Tracks costs for agent operations.
    
    Supports multiple pricing models and cost aggregation by agent, operation, or model.
    """
    
    def __init__(self, default_pricing: Optional[Dict[str, ModelPricing]] = None):
        """
        Initialize cost tracker.
        
        Args:
            default_pricing: Dictionary of model_id -> ModelPricing
        """
        self.pricing_models: Dict[str, ModelPricing] = default_pricing or {}
        self.operations: List[OperationCost] = []
        self._operation_index: Dict[str, OperationCost] = {}
    
    def register_pricing(self, pricing: ModelPricing) -> None:
        """Register a pricing model."""
        self.pricing_models[pricing.model_id] = pricing
    
    def register_multiple_pricing(self, pricing_list: List[ModelPricing]) -> None:
        """Register multiple pricing models."""
        for pricing in pricing_list:
            self.register_pricing(pricing)
    
    def record_operation(
        self,
        operation_id: str,
        operation_name: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        metadata: Optional[Dict] = None
    ) -> OperationCost:
        """
        Record an operation and its cost.
        
        Args:
            operation_id: Unique identifier for operation
            operation_name: Name of the operation
            model_id: Model used for operation
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            metadata: Additional metadata
            
        Returns:
            OperationCost with calculated cost
            
        Raises:
            ValueError: If model_id not found in pricing
        """
        if model_id not in self.pricing_models:
            raise ValueError(f"Model {model_id} not found in pricing models")
        
        pricing = self.pricing_models[model_id]
        token_usage = TokenUsage(input_tokens, output_tokens)
        cost = pricing.calculate_total_cost(input_tokens, output_tokens)
        
        operation = OperationCost(
            operation_id=operation_id,
            operation_name=operation_name,
            model_id=model_id,
            token_usage=token_usage,
            cost=cost,
            metadata=metadata or {}
        )
        
        self.operations.append(operation)
        self._operation_index[operation_id] = operation
        
        return operation
    
    def get_operation(self, operation_id: str) -> Optional[OperationCost]:
        """Get a specific operation by ID."""
        return self._operation_index.get(operation_id)
    
    def get_agent_costs(
        self,
        agent_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> CostSummary:
        """
        Get cost summary for an agent.
        
        Args:
            agent_id: Agent identifier (from metadata)
            start_time: Start of period (optional)
            end_time: End of period (optional)
            
        Returns:
            CostSummary with aggregated costs
        """
        filtered_ops = [
            op for op in self.operations
            if op.metadata.get("agent_id") == agent_id
        ]
        
        if start_time:
            filtered_ops = [op for op in filtered_ops if op.timestamp >= start_time]
        if end_time:
            filtered_ops = [op for op in filtered_ops if op.timestamp <= end_time]
        
        return self._calculate_summary(agent_id, filtered_ops, start_time, end_time)
    
    def get_model_costs(
        self,
        model_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> CostSummary:
        """Get cost summary for a specific model."""
        filtered_ops = [op for op in self.operations if op.model_id == model_id]
        
        if start_time:
            filtered_ops = [op for op in filtered_ops if op.timestamp >= start_time]
        if end_time:
            filtered_ops = [op for op in filtered_ops if op.timestamp <= end_time]
        
        return self._calculate_summary(f"model:{model_id}", filtered_ops, start_time, end_time)
    
    def get_operation_costs(
        self,
        operation_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> CostSummary:
        """Get cost summary for a specific operation type."""
        filtered_ops = [
            op for op in self.operations
            if op.operation_name == operation_name
        ]
        
        if start_time:
            filtered_ops = [op for op in filtered_ops if op.timestamp >= start_time]
        if end_time:
            filtered_ops = [op for op in filtered_ops if op.timestamp <= end_time]
        
        return self._calculate_summary(
            f"operation:{operation_name}",
            filtered_ops,
            start_time,
            end_time
        )
    
    def get_total_costs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> CostSummary:
        """Get total costs across all operations."""
        filtered_ops = self.operations
        
        if start_time:
            filtered_ops = [op for op in filtered_ops if op.timestamp >= start_time]
        if end_time:
            filtered_ops = [op for op in filtered_ops if op.timestamp <= end_time]
        
        return self._calculate_summary("total", filtered_ops, start_time, end_time)
    
    def _calculate_summary(
        self,
        identifier: str,
        operations: List[OperationCost],
        start_time: Optional[datetime],
        end_time: Optional[datetime]
    ) -> CostSummary:
        """Calculate cost summary from list of operations."""
        summary = CostSummary(
            agent_id=identifier,
            period_start=start_time or (operations[0].timestamp if operations else datetime.now()),
            period_end=end_time or (operations[-1].timestamp if operations else datetime.now())
        )
        
        for op in operations:
            summary.total_cost += op.cost
            summary.total_input_tokens += op.token_usage.input_tokens
            summary.total_output_tokens += op.token_usage.output_tokens
            summary.operation_count += 1
            
            # Aggregate by model
            if op.model_id not in summary.cost_by_model:
                summary.cost_by_model[op.model_id] = 0.0
            summary.cost_by_model[op.model_id] += op.cost
            
            # Aggregate by operation
            if op.operation_name not in summary.cost_by_operation:
                summary.cost_by_operation[op.operation_name] = 0.0
            summary.cost_by_operation[op.operation_name] += op.cost
        
        return summary
    
    def export_to_json(self, filepath: str) -> None:
        """Export all operation costs to JSON file."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "operations": [op.to_dict() for op in self.operations],
            "pricing_models": {k: v.to_dict() for k, v in self.pricing_models.items()},
            "total": self.get_total_costs().to_dict()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def clear_operations(self) -> None:
        """Clear all recorded operations."""
        self.operations.clear()
        self._operation_index.clear()


# Common pricing configurations (as of 2024)
OPENAI_PRICING = {
    "gpt-4-turbo": ModelPricing(
        model_id="gpt-4-turbo",
        input_price_per_1k=0.01,
        output_price_per_1k=0.03,
        name="GPT-4 Turbo",
        provider="openai"
    ),
    "gpt-4": ModelPricing(
        model_id="gpt-4",
        input_price_per_1k=0.03,
        output_price_per_1k=0.06,
        name="GPT-4",
        provider="openai"
    ),
    "gpt-3.5-turbo": ModelPricing(
        model_id="gpt-3.5-turbo",
        input_price_per_1k=0.0005,
        output_price_per_1k=0.0015,
        name="GPT-3.5 Turbo",
        provider="openai"
    )
}

ANTHROPIC_PRICING = {
    "claude-3-opus": ModelPricing(
        model_id="claude-3-opus",
        input_price_per_1k=0.015,
        output_price_per_1k=0.075,
        name="Claude 3 Opus",
        provider="anthropic"
    ),
    "claude-3-sonnet": ModelPricing(
        model_id="claude-3-sonnet",
        input_price_per_1k=0.003,
        output_price_per_1k=0.015,
        name="Claude 3 Sonnet",
        provider="anthropic"
    ),
    "claude-3-haiku": ModelPricing(
        model_id="claude-3-haiku",
        input_price_per_1k=0.00025,
        output_price_per_1k=0.00125,
        name="Claude 3 Haiku",
        provider="anthropic"
    )
}


def create_cost_tracker(pricing_preset: str = "openai") -> CostTracker:
    """
    Create a cost tracker with predefined pricing.
    
    Args:
        pricing_preset: "openai", "anthropic", or "combined"
        
    Returns:
        CostTracker instance
    """
    pricing_map = {
        "openai": OPENAI_PRICING,
        "anthropic": ANTHROPIC_PRICING,
        "combined": {**OPENAI_PRICING, **ANTHROPIC_PRICING}
    }
    
    pricing = pricing_map.get(pricing_preset, OPENAI_PRICING)
    return CostTracker(pricing)
