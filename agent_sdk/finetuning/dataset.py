"""Fine-tuning dataset management and utilities."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import json
import hashlib
from enum import Enum


class DatasetFormat(Enum):
    """Supported dataset formats."""
    JSONL = "jsonl"
    JSON = "json"
    CSV = "csv"
    HUGGINGFACE = "huggingface"


@dataclass
class TrainingExample:
    """Single training example for fine-tuning.
    
    Attributes:
        prompt: Input text/prompt
        completion: Expected output/completion
        metadata: Additional metadata (difficulty, source, etc.)
        weight: Importance weight (0.0-1.0)
    """
    
    prompt: str
    completion: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt": self.prompt,
            "completion": self.completion,
            "metadata": self.metadata,
            "weight": self.weight,
        }
    
    def get_tokens(self) -> int:
        """Estimate token count (rough approximation)."""
        text = self.prompt + self.completion
        return len(text) // 4 + 1
    
    def hash(self) -> str:
        """Get unique hash of example."""
        content = f"{self.prompt}:{self.completion}"
        return hashlib.md5(content.encode()).hexdigest()


@dataclass
class DatasetMetrics:
    """Metrics about a dataset.
    
    Attributes:
        total_examples: Total number of examples
        total_tokens: Estimated total tokens
        avg_prompt_length: Average prompt length in chars
        avg_completion_length: Average completion length in chars
        unique_prompts: Number of unique prompts
        duplicates: Number of duplicate examples
        avg_weight: Average example weight
    """
    
    total_examples: int = 0
    total_tokens: int = 0
    avg_prompt_length: float = 0.0
    avg_completion_length: float = 0.0
    unique_prompts: int = 0
    duplicates: int = 0
    avg_weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_examples": self.total_examples,
            "total_tokens": self.total_tokens,
            "avg_prompt_length": self.avg_prompt_length,
            "avg_completion_length": self.avg_completion_length,
            "unique_prompts": self.unique_prompts,
            "duplicates": self.duplicates,
            "avg_weight": self.avg_weight,
        }


class TrainingDataset:
    """Container and manager for training examples.
    
    Provides utilities for loading, validating, and preprocessing
    training datasets for fine-tuning.
    """
    
    def __init__(self, examples: Optional[List[TrainingExample]] = None, 
                 name: str = "training_dataset",
                 max_tokens: int = 4000000):
        """Initialize dataset.
        
        Args:
            examples: Initial examples
            name: Dataset name
            max_tokens: Maximum total tokens allowed
        """
        self.name = name
        self.max_tokens = max_tokens
        self.examples: List[TrainingExample] = examples or []
        self.created_at = datetime.utcnow()
        self._hash_to_example: Dict[str, TrainingExample] = {}
        self._build_index()
    
    def _build_index(self) -> None:
        """Build hash index for deduplication."""
        for example in self.examples:
            self._hash_to_example[example.hash()] = example
    
    def add_example(self, example: TrainingExample) -> bool:
        """Add example to dataset.
        
        Args:
            example: Example to add
            
        Returns:
            True if added, False if duplicate
        """
        # Check duplicate
        ex_hash = example.hash()
        if ex_hash in self._hash_to_example:
            return False
        
        # Check token budget
        if self.get_metrics().total_tokens + example.get_tokens() > self.max_tokens:
            return False
        
        self.examples.append(example)
        self._hash_to_example[ex_hash] = example
        return True
    
    def add_examples(self, examples: List[TrainingExample]) -> Tuple[int, int]:
        """Add multiple examples.
        
        Args:
            examples: Examples to add
            
        Returns:
            Tuple of (added_count, skipped_count)
        """
        added = 0
        skipped = 0
        for example in examples:
            if self.add_example(example):
                added += 1
            else:
                skipped += 1
        return added, skipped
    
    def remove_example(self, example: TrainingExample) -> bool:
        """Remove example from dataset."""
        try:
            self.examples.remove(example)
            del self._hash_to_example[example.hash()]
            return True
        except (ValueError, KeyError):
            return False
    
    def get_metrics(self) -> DatasetMetrics:
        """Calculate dataset metrics."""
        if not self.examples:
            return DatasetMetrics()
        
        total_tokens = sum(ex.get_tokens() for ex in self.examples)
        total_prompt_len = sum(len(ex.prompt) for ex in self.examples)
        total_completion_len = sum(len(ex.completion) for ex in self.examples)
        avg_weight = sum(ex.weight for ex in self.examples) / len(self.examples)
        
        unique_prompts = len(set(ex.prompt for ex in self.examples))
        duplicates = len(self.examples) - len(self._hash_to_example)
        
        return DatasetMetrics(
            total_examples=len(self.examples),
            total_tokens=total_tokens,
            avg_prompt_length=total_prompt_len / len(self.examples),
            avg_completion_length=total_completion_len / len(self.examples),
            unique_prompts=unique_prompts,
            duplicates=duplicates,
            avg_weight=avg_weight,
        )
    
    def split(self, train_ratio: float = 0.8) -> Tuple['TrainingDataset', 'TrainingDataset']:
        """Split dataset into train/test sets.
        
        Args:
            train_ratio: Ratio for training set (0.0-1.0)
            
        Returns:
            Tuple of (train_dataset, test_dataset)
        """
        split_idx = int(len(self.examples) * train_ratio)
        train_examples = self.examples[:split_idx]
        test_examples = self.examples[split_idx:]
        
        return (
            TrainingDataset(train_examples, f"{self.name}_train", self.max_tokens),
            TrainingDataset(test_examples, f"{self.name}_test", self.max_tokens),
        )
    
    def filter_by_weight(self, min_weight: float = 0.0) -> 'TrainingDataset':
        """Filter examples by minimum weight.
        
        Args:
            min_weight: Minimum weight threshold
            
        Returns:
            New filtered dataset
        """
        filtered = [ex for ex in self.examples if ex.weight >= min_weight]
        return TrainingDataset(filtered, f"{self.name}_filtered", self.max_tokens)
    
    def to_jsonl(self) -> str:
        """Convert to JSONL format."""
        lines = [json.dumps(ex.to_dict()) for ex in self.examples]
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        metrics = self.get_metrics()
        return {
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "example_count": len(self.examples),
            "metrics": metrics.to_dict(),
            "examples": [ex.to_dict() for ex in self.examples],
        }
    
    @classmethod
    def from_jsonl(cls, content: str, name: str = "dataset") -> 'TrainingDataset':
        """Load from JSONL format.
        
        Args:
            content: JSONL content
            name: Dataset name
            
        Returns:
            New TrainingDataset
        """
        examples = []
        for line in content.strip().split("\n"):
            if line:
                data = json.loads(line)
                example = TrainingExample(
                    prompt=data["prompt"],
                    completion=data["completion"],
                    metadata=data.get("metadata", {}),
                    weight=data.get("weight", 1.0),
                )
                examples.append(example)
        return cls(examples, name)
