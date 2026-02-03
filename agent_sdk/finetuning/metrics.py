"""Training and evaluation metrics."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class TrainingMetrics:
    """Metrics from training run.
    
    Attributes:
        epoch: Current epoch
        loss: Training loss
        learning_rate: Current learning rate
        tokens_processed: Tokens processed
        examples_processed: Examples processed
        timestamp: Metric timestamp
    """
    
    epoch: int = 0
    loss: float = 0.0
    learning_rate: float = 0.0001
    tokens_processed: int = 0
    examples_processed: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "epoch": self.epoch,
            "loss": round(self.loss, 4),
            "learning_rate": self.learning_rate,
            "tokens_processed": self.tokens_processed,
            "examples_processed": self.examples_processed,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class EvaluationMetrics:
    """Evaluation metrics for fine-tuned model.
    
    Attributes:
        accuracy: Accuracy on test set
        bleu_score: BLEU score for text generation
        perplexity: Model perplexity
        f1_score: F1 score if classification
        precision: Precision if classification
        recall: Recall if classification
        latency_ms: Average latency in ms
        throughput: Examples per second
        metadata: Additional metrics
    """
    
    accuracy: Optional[float] = None
    bleu_score: Optional[float] = None
    perplexity: Optional[float] = None
    f1_score: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    latency_ms: Optional[float] = None
    throughput: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        if self.accuracy is not None:
            result["accuracy"] = round(self.accuracy, 4)
        if self.bleu_score is not None:
            result["bleu_score"] = round(self.bleu_score, 4)
        if self.perplexity is not None:
            result["perplexity"] = round(self.perplexity, 4)
        if self.f1_score is not None:
            result["f1_score"] = round(self.f1_score, 4)
        if self.precision is not None:
            result["precision"] = round(self.precision, 4)
        if self.recall is not None:
            result["recall"] = round(self.recall, 4)
        if self.latency_ms is not None:
            result["latency_ms"] = round(self.latency_ms, 2)
        if self.throughput is not None:
            result["throughput"] = round(self.throughput, 2)
        
        result["metadata"] = self.metadata
        result["timestamp"] = self.timestamp.isoformat()
        return result
    
    def get_score(self) -> float:
        """Get composite score (0.0-1.0).
        
        Weights: accuracy (0.4), bleu (0.3), f1 (0.3)
        """
        score = 0.0
        weight_sum = 0.0
        
        if self.accuracy is not None:
            score += self.accuracy * 0.4
            weight_sum += 0.4
        if self.bleu_score is not None:
            score += self.bleu_score * 0.3
            weight_sum += 0.3
        if self.f1_score is not None:
            score += self.f1_score * 0.3
            weight_sum += 0.3
        
        return score / weight_sum if weight_sum > 0 else 0.0
