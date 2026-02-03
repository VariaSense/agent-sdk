"""Tests for fine-tuning module."""

import pytest
import asyncio
from agent_sdk.finetuning.dataset import TrainingExample, TrainingDataset, DatasetMetrics
from agent_sdk.finetuning.job import TrainingJob, TrainingJobConfig, TrainingJobStatus
from agent_sdk.finetuning.metrics import TrainingMetrics, EvaluationMetrics
from agent_sdk.finetuning.adapter import ModelAdapter, AdapterConfig
from agent_sdk.finetuning.orchestrator import FineTuningOrchestrator


class TestTrainingExample:
    """Test TrainingExample class."""
    
    def test_create_example(self):
        """Test creating a training example."""
        example = TrainingExample(
            prompt="What is 2+2?",
            completion="4",
            weight=0.9
        )
        assert example.prompt == "What is 2+2?"
        assert example.completion == "4"
        assert example.weight == 0.9
    
    def test_example_to_dict(self):
        """Test example serialization."""
        example = TrainingExample("Q", "A", {"type": "math"}, 0.8)
        result = example.to_dict()
        assert result["prompt"] == "Q"
        assert result["completion"] == "A"
        assert result["metadata"]["type"] == "math"
        assert result["weight"] == 0.8
    
    def test_example_token_count(self):
        """Test token count estimation."""
        example = TrainingExample("hello world", "goodbye")
        tokens = example.get_tokens()
        assert tokens > 0
    
    def test_example_hash(self):
        """Test example hashing."""
        ex1 = TrainingExample("Q", "A")
        ex2 = TrainingExample("Q", "A")
        assert ex1.hash() == ex2.hash()
        
        ex3 = TrainingExample("Q", "B")
        assert ex1.hash() != ex3.hash()


class TestTrainingDataset:
    """Test TrainingDataset class."""
    
    def test_create_empty_dataset(self):
        """Test creating an empty dataset."""
        dataset = TrainingDataset(name="test")
        assert dataset.name == "test"
        assert len(dataset.examples) == 0
    
    def test_add_example(self):
        """Test adding an example."""
        dataset = TrainingDataset()
        example = TrainingExample("Q", "A")
        added = dataset.add_example(example)
        assert added is True
        assert len(dataset.examples) == 1
    
    def test_add_duplicate_example(self):
        """Test adding duplicate examples."""
        dataset = TrainingDataset()
        ex1 = TrainingExample("Q", "A")
        added1 = dataset.add_example(ex1)
        added2 = dataset.add_example(ex1)
        assert added1 is True
        assert added2 is False
        assert len(dataset.examples) == 1
    
    def test_add_multiple_examples(self):
        """Test adding multiple examples."""
        dataset = TrainingDataset()
        examples = [
            TrainingExample(f"Q{i}", f"A{i}")
            for i in range(5)
        ]
        added, skipped = dataset.add_examples(examples)
        assert added == 5
        assert skipped == 0
        assert len(dataset.examples) == 5
    
    def test_get_metrics(self):
        """Test dataset metrics."""
        dataset = TrainingDataset()
        examples = [
            TrainingExample("Question", "Answer", weight=0.9),
            TrainingExample("Q", "A", weight=0.8),
        ]
        dataset.add_examples(examples)
        
        metrics = dataset.get_metrics()
        assert metrics.total_examples == 2
        assert metrics.total_tokens > 0
        assert 0.8 <= metrics.avg_weight <= 0.9
    
    def test_split_dataset(self):
        """Test splitting dataset."""
        dataset = TrainingDataset()
        examples = [TrainingExample(f"Q{i}", f"A{i}") for i in range(10)]
        dataset.add_examples(examples)
        
        train, test = dataset.split(0.8)
        assert len(train.examples) == 8
        assert len(test.examples) == 2
        assert len(train.examples) + len(test.examples) == 10
    
    def test_filter_by_weight(self):
        """Test filtering by weight."""
        dataset = TrainingDataset()
        examples = [
            TrainingExample("Q1", "A1", weight=0.9),
            TrainingExample("Q2", "A2", weight=0.5),
            TrainingExample("Q3", "A3", weight=0.8),
        ]
        dataset.add_examples(examples)
        
        filtered = dataset.filter_by_weight(0.7)
        assert len(filtered.examples) == 2
    
    def test_to_jsonl(self):
        """Test JSONL conversion."""
        dataset = TrainingDataset()
        examples = [TrainingExample("Q", "A"), TrainingExample("Q2", "A2")]
        dataset.add_examples(examples)
        
        jsonl = dataset.to_jsonl()
        assert "Q" in jsonl
        assert "A" in jsonl
    
    def test_from_jsonl(self):
        """Test loading from JSONL."""
        jsonl = '{"prompt": "Q1", "completion": "A1"}\n{"prompt": "Q2", "completion": "A2"}'
        dataset = TrainingDataset.from_jsonl(jsonl)
        assert len(dataset.examples) == 2
        assert dataset.examples[0].prompt == "Q1"


class TestTrainingJob:
    """Test TrainingJob class."""
    
    def test_create_job(self):
        """Test creating a training job."""
        job = TrainingJob(config=TrainingJobConfig())
        assert job.status == TrainingJobStatus.CREATED
        assert job.job_id is not None
    
    def test_job_start(self):
        """Test starting a job."""
        job = TrainingJob()
        job.start()
        assert job.status == TrainingJobStatus.RUNNING
        assert job.started_at is not None
    
    def test_job_complete(self):
        """Test completing a job."""
        job = TrainingJob()
        job.start()
        job.complete("model-123", {"loss": 0.042})
        assert job.status == TrainingJobStatus.COMPLETED
        assert job.model_id == "model-123"
        assert job.metrics["loss"] == 0.042
    
    def test_job_fail(self):
        """Test failing a job."""
        job = TrainingJob()
        job.start()
        job.fail("Out of memory")
        assert job.status == TrainingJobStatus.FAILED
        assert "Out of memory" in job.error_message
    
    def test_job_cancel(self):
        """Test cancelling a job."""
        job = TrainingJob()
        job.cancel()
        assert job.status == TrainingJobStatus.CANCELLED
    
    def test_job_get_duration(self):
        """Test getting job duration."""
        job = TrainingJob()
        job.start()
        import time
        time.sleep(0.01)
        job.complete("model-123", {})
        duration = job.get_duration()
        assert duration > 0


class TestEvaluationMetrics:
    """Test EvaluationMetrics class."""
    
    def test_create_metrics(self):
        """Test creating evaluation metrics."""
        metrics = EvaluationMetrics(
            accuracy=0.95,
            bleu_score=0.88,
            f1_score=0.91
        )
        assert metrics.accuracy == 0.95
        assert metrics.bleu_score == 0.88
    
    def test_metrics_to_dict(self):
        """Test metrics serialization."""
        metrics = EvaluationMetrics(accuracy=0.95, bleu_score=0.88)
        result = metrics.to_dict()
        assert result["accuracy"] == 0.95
        assert result["bleu_score"] == 0.88
        assert "timestamp" in result
    
    def test_get_composite_score(self):
        """Test composite score calculation."""
        metrics = EvaluationMetrics(accuracy=1.0, bleu_score=1.0, f1_score=1.0)
        score = metrics.get_score()
        assert abs(score - 1.0) < 0.01


class TestModelAdapter:
    """Test ModelAdapter class."""
    
    def test_create_adapter(self):
        """Test creating a model adapter."""
        adapter = ModelAdapter("model-123")
        assert adapter.model_id == "model-123"
        assert adapter.is_active is True
    
    def test_activate_deactivate(self):
        """Test adapter activation."""
        adapter = ModelAdapter("model-123")
        adapter.deactivate()
        assert adapter.is_active is False
        adapter.activate()
        assert adapter.is_active is True
    
    def test_record_inference(self):
        """Test recording inference."""
        adapter = ModelAdapter("model-123")
        adapter.record_inference(100)
        adapter.record_inference(120)
        assert adapter.inference_count == 2
        assert adapter.total_tokens == 220


class TestFineTuningOrchestrator:
    """Test FineTuningOrchestrator class."""
    
    @pytest.mark.asyncio
    async def test_create_dataset(self):
        """Test dataset creation."""
        orchestrator = FineTuningOrchestrator()
        dataset = orchestrator.create_dataset("test")
        assert dataset.name == "test"
        assert orchestrator.get_dataset("test") is not None
    
    @pytest.mark.asyncio
    async def test_submit_training_job(self):
        """Test submitting a training job."""
        orchestrator = FineTuningOrchestrator()
        dataset = orchestrator.create_dataset("train")
        dataset.add_example(TrainingExample("Q", "A"))
        
        job = await orchestrator.submit_training_job(dataset)
        assert job.job_id in orchestrator.jobs
        assert job.training_examples == 1
        
        # Wait for completion
        await asyncio.sleep(0.2)
        assert job.status == TrainingJobStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_evaluate_model(self):
        """Test model evaluation."""
        orchestrator = FineTuningOrchestrator()
        dataset = orchestrator.create_dataset("train")
        dataset.add_example(TrainingExample("Q", "A"))
        
        job = await orchestrator.submit_training_job(dataset)
        await asyncio.sleep(0.2)
        
        test_dataset = orchestrator.create_dataset("test")
        test_dataset.add_example(TrainingExample("Q2", "A2"))
        
        metrics = await orchestrator.evaluate(job, test_dataset)
        assert metrics.accuracy > 0
        assert metrics.bleu_score > 0
    
    @pytest.mark.asyncio
    async def test_list_jobs(self):
        """Test listing jobs."""
        orchestrator = FineTuningOrchestrator()
        dataset = orchestrator.create_dataset("train")
        dataset.add_example(TrainingExample("Q", "A"))
        
        job1 = await orchestrator.submit_training_job(dataset)
        job2 = await orchestrator.submit_training_job(dataset)
        
        all_jobs = orchestrator.list_jobs()
        assert len(all_jobs) == 2
    
    @pytest.mark.asyncio
    async def test_adapter_management(self):
        """Test adapter activation and deactivation."""
        orchestrator = FineTuningOrchestrator()
        dataset = orchestrator.create_dataset("train")
        dataset.add_example(TrainingExample("Q", "A"))
        
        job = await orchestrator.submit_training_job(dataset)
        await asyncio.sleep(0.2)
        
        assert job.model_id is not None
        assert orchestrator.activate_adapter(job.model_id) is True
        
        adapter = orchestrator.get_adapter(job.model_id)
        assert adapter.is_active is True
        
        orchestrator.deactivate_adapter(job.model_id)
        assert adapter.is_active is False
