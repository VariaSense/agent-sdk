"""Fine-tuning job management and tracking."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime
from enum import Enum
import uuid


class TrainingJobStatus(Enum):
    """Status of a training job."""
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Alias for backwards compatibility
JobStatus = TrainingJobStatus


@dataclass
class TrainingJobConfig:
    """Configuration for training job.
    
    Attributes:
        base_model: Model to fine-tune
        learning_rate: Learning rate for training
        batch_size: Batch size for training
        epochs: Number of training epochs
        warmup_steps: Number of warmup steps
        max_tokens: Maximum tokens per example
        weight_decay: Weight decay regularization
        gradient_clip_norm: Gradient clipping norm
    """
    
    base_model: str = "gpt-3.5-turbo"
    learning_rate: float = 0.0001
    batch_size: int = 4
    epochs: int = 3
    warmup_steps: int = 100
    max_tokens: int = 512
    weight_decay: float = 0.01
    gradient_clip_norm: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "base_model": self.base_model,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "epochs": self.epochs,
            "warmup_steps": self.warmup_steps,
            "max_tokens": self.max_tokens,
            "weight_decay": self.weight_decay,
            "gradient_clip_norm": self.gradient_clip_norm,
        }


@dataclass
class TrainingJob:
    """Represents a fine-tuning job.
    
    Attributes:
        job_id: Unique job identifier
        config: Training configuration
        status: Current job status
        created_at: Job creation timestamp
        started_at: Job start timestamp
        completed_at: Job completion timestamp
        training_examples: Number of training examples
        error_message: Error message if failed
        model_id: ID of fine-tuned model
        metrics: Training metrics (loss, accuracy, etc.)
    """
    
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config: TrainingJobConfig = field(default_factory=TrainingJobConfig)
    status: TrainingJobStatus = TrainingJobStatus.CREATED
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    training_examples: int = 0
    error_message: Optional[str] = None
    model_id: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    
    def start(self) -> None:
        """Mark job as started."""
        self.status = TrainingJobStatus.RUNNING
        self.started_at = datetime.utcnow()
    
    def complete(self, model_id: str, metrics: Dict[str, float]) -> None:
        """Mark job as completed.
        
        Args:
            model_id: ID of fine-tuned model
            metrics: Training metrics
        """
        self.status = TrainingJobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.model_id = model_id
        self.metrics = metrics
    
    def fail(self, error: str) -> None:
        """Mark job as failed.
        
        Args:
            error: Error message
        """
        self.status = TrainingJobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error
    
    def cancel(self) -> None:
        """Cancel the job."""
        self.status = TrainingJobStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def get_duration(self) -> Optional[float]:
        """Get job duration in seconds.
        
        Returns:
            Duration in seconds, or None if not completed
        """
        start = self.started_at or self.created_at
        end = self.completed_at or datetime.utcnow()
        delta = end - start
        return delta.total_seconds()
    
    def get_progress(self) -> float:
        """Estimate job progress (0.0-1.0)."""
        if self.status == TrainingJobStatus.COMPLETED:
            return 1.0
        elif self.status == TrainingJobStatus.FAILED:
            return 0.0
        elif self.status == TrainingJobStatus.RUNNING:
            # Simulate progress based on time elapsed
            if self.started_at:
                elapsed = (datetime.utcnow() - self.started_at).total_seconds()
                # Assume 5 minute training window for progress calculation
                progress = min(0.9, elapsed / 300.0)
                return progress
        return 0.0 if self.status == TrainingJobStatus.QUEUED else 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "config": self.config.to_dict(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "training_examples": self.training_examples,
            "error_message": self.error_message,
            "model_id": self.model_id,
            "metrics": self.metrics,
            "progress": self.get_progress(),
        }
