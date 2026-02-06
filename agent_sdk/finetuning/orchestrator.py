"""Fine-tuning orchestrator for managing training workflows."""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum

from agent_sdk.finetuning.dataset import TrainingDataset
from agent_sdk.finetuning.job import TrainingJob, TrainingJobConfig, TrainingJobStatus
from agent_sdk.finetuning.metrics import TrainingMetrics, EvaluationMetrics
from agent_sdk.finetuning.adapter import ModelAdapter, AdapterConfig


class TrainingStrategy(Enum):
    """Strategy for training."""
    STANDARD = "standard"
    DISTRIBUTED = "distributed"
    FEDERATED = "federated"


@dataclass
class TrainingResult:
    """Result of a training job.
    
    Attributes:
        job_id: Training job ID
        success: Whether training succeeded
        model_id: ID of fine-tuned model
        metrics: Final metrics
        duration_seconds: Training duration
        cost: Estimated cost
        error: Error message if failed
    """
    
    job_id: str
    success: bool
    model_id: Optional[str] = None
    metrics: Optional[Dict[str, float]] = None
    duration_seconds: float = 0.0
    cost: float = 0.0
    error: Optional[str] = None


class FineTuningOrchestrator:
    """Orchestrate fine-tuning workflows.
    
    Manages dataset loading, training job execution, model adaptation,
    and evaluation of fine-tuned models.
    """
    
    def __init__(self, max_concurrent_jobs: int = 3):
        """Initialize orchestrator.
        
        Args:
            max_concurrent_jobs: Max concurrent training jobs
        """
        self.max_concurrent_jobs = max_concurrent_jobs
        self.jobs: Dict[str, TrainingJob] = {}
        self.adapters: Dict[str, ModelAdapter] = {}
        self.datasets: Dict[str, TrainingDataset] = {}
        self._running_jobs = 0
    
    def create_dataset(self, name: str, examples: Optional[List] = None) -> TrainingDataset:
        """Create a training dataset.
        
        Args:
            name: Dataset name
            examples: Optional examples
            
        Returns:
            TrainingDataset instance
        """
        dataset = TrainingDataset(examples, name)
        self.datasets[name] = dataset
        return dataset
    
    def get_dataset(self, name: str) -> Optional[TrainingDataset]:
        """Get dataset by name."""
        return self.datasets.get(name)
    
    async def submit_training_job(
        self,
        dataset: TrainingDataset,
        config: Optional[TrainingJobConfig] = None,
        background: bool = False,
    ) -> TrainingJob:
        """Submit a training job.
        
        Args:
            dataset: Training dataset
            config: Training configuration
            background: Run job asynchronously if True
            
        Returns:
            TrainingJob instance
        """
        # Create job
        job = TrainingJob(
            config=config or TrainingJobConfig(),
            training_examples=len(dataset.examples),
        )
        
        # Store job
        self.jobs[job.job_id] = job
        
        # Submit for execution
        if background:
            asyncio.create_task(self._execute_job(job, dataset))
        else:
            await self._execute_job(job, dataset)
        
        return job
    
    async def _execute_job(self, job: TrainingJob, dataset: TrainingDataset) -> None:
        """Execute training job internally.
        
        Args:
            job: Training job
            dataset: Training dataset
        """
        try:
            # Wait for slot if needed
            while self._running_jobs >= self.max_concurrent_jobs:
                await asyncio.sleep(0.1)
            
            self._running_jobs += 1
            job.start()
            
            # Simulate training
            await asyncio.sleep(0.1)  # Simulated training
            
            # Generate metrics
            metrics = {
                "final_loss": 0.042,
                "accuracy": 0.94,
                "precision": 0.92,
                "recall": 0.95,
            }
            
            # Create fine-tuned model
            model_id = f"ft-{job.config.base_model}-{uuid.uuid4().hex[:8]}"
            adapter = ModelAdapter(model_id, AdapterConfig(base_model=job.config.base_model))
            self.adapters[model_id] = adapter
            
            # Mark complete
            job.complete(model_id, metrics)
            
        except Exception as e:
            job.fail(str(e))
        finally:
            self._running_jobs -= 1
    
    async def evaluate(
        self,
        job: TrainingJob,
        test_dataset: TrainingDataset,
    ) -> EvaluationMetrics:
        """Evaluate a fine-tuned model.
        
        Args:
            job: Training job with fine-tuned model
            test_dataset: Test dataset for evaluation
            
        Returns:
            EvaluationMetrics
        """
        if not job.model_id:
            raise ValueError("Job not completed or model_id not set")
        
        # Simulate evaluation
        await asyncio.sleep(0.05)
        
        metrics = EvaluationMetrics(
            accuracy=0.92,
            bleu_score=0.85,
            f1_score=0.89,
            latency_ms=125.5,
            throughput=8.0,
        )
        
        return metrics
    
    def get_job(self, job_id: str) -> Optional[TrainingJob]:
        """Get training job by ID."""
        return self.jobs.get(job_id)
    
    def list_jobs(self, status: Optional[TrainingJobStatus] = None) -> List[TrainingJob]:
        """List training jobs.
        
        Args:
            status: Filter by status
            
        Returns:
            List of TrainingJob instances
        """
        jobs = list(self.jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs
    
    def get_adapter(self, model_id: str) -> Optional[ModelAdapter]:
        """Get model adapter by ID."""
        return self.adapters.get(model_id)
    
    def activate_adapter(self, model_id: str) -> bool:
        """Activate a model adapter.
        
        Args:
            model_id: Model ID
            
        Returns:
            True if activated
        """
        adapter = self.adapters.get(model_id)
        if adapter:
            adapter.activate()
            return True
        return False
    
    def deactivate_adapter(self, model_id: str) -> bool:
        """Deactivate a model adapter.
        
        Args:
            model_id: Model ID
            
        Returns:
            True if deactivated
        """
        adapter = self.adapters.get(model_id)
        if adapter:
            adapter.deactivate()
            return True
        return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get orchestrator system status."""
        job_statuses = {}
        for status in TrainingJobStatus:
            job_statuses[status.value] = len([j for j in self.jobs.values() if j.status == status])
        
        return {
            "running_jobs": self._running_jobs,
            "max_concurrent": self.max_concurrent_jobs,
            "total_jobs": len(self.jobs),
            "job_statuses": job_statuses,
            "adapters": len(self.adapters),
            "datasets": len(self.datasets),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "total_jobs": len(self.jobs),
            "total_adapters": len(self.adapters),
            "total_datasets": len(self.datasets),
            "running_jobs": self._running_jobs,
            "status": self.get_system_status(),
        }
