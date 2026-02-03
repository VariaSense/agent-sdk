"""Fine-tuning module for model adaptation and training.

This module provides tools for managing fine-tuning datasets, orchestrating
training jobs, tracking training progress, and evaluating fine-tuned models.

Classes:
    TrainingDataset: Container for training examples
    TrainingJob: Configuration and execution of training
    TrainingMetrics: Metrics from training run
    FineTuningOrchestrator: Orchestrate fine-tuning workflows
    ModelAdapter: Adapter for fine-tuned models

Usage:
    from agent_sdk.finetuning import FineTuningOrchestrator
    
    orchestrator = FineTuningOrchestrator()
    dataset = orchestrator.load_dataset("examples.jsonl")
    job = await orchestrator.train(dataset, base_model="gpt-3.5-turbo")
    result = await orchestrator.evaluate(job)
"""

from agent_sdk.finetuning.dataset import (
    TrainingExample,
    TrainingDataset,
    DatasetMetrics,
)
from agent_sdk.finetuning.job import (
    TrainingJobStatus,
    TrainingJob,
    TrainingJobConfig,
    JobStatus,
)
from agent_sdk.finetuning.metrics import (
    TrainingMetrics,
    EvaluationMetrics,
)
from agent_sdk.finetuning.orchestrator import (
    FineTuningOrchestrator,
    TrainingResult,
)
from agent_sdk.finetuning.adapter import (
    ModelAdapter,
    AdapterConfig,
)

__all__ = [
    "TrainingExample",
    "TrainingDataset",
    "DatasetMetrics",
    "TrainingJobStatus",
    "TrainingJob",
    "TrainingJobConfig",
    "JobStatus",
    "TrainingMetrics",
    "EvaluationMetrics",
    "FineTuningOrchestrator",
    "TrainingResult",
    "ModelAdapter",
    "AdapterConfig",
]
