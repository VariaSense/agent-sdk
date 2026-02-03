"""Prompt management system with versioning, A/B testing, and evaluation."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
from datetime import datetime
import json
import hashlib


class PromptTier(Enum):
    """Prompt quality/complexity tiers."""
    
    SIMPLE = "simple"              # Basic prompts, few variables
    STANDARD = "standard"          # Standard complexity, moderate variables
    ADVANCED = "advanced"          # Complex reasoning, many variables
    EXPERT = "expert"              # Maximum complexity, optimization


class EvaluationMetric(Enum):
    """Metrics for prompt evaluation."""
    
    ACCURACY = "accuracy"          # Correctness of output
    RELEVANCE = "relevance"        # Relevance to query
    COHERENCE = "coherence"        # Logical consistency
    CLARITY = "clarity"            # Output clarity
    EFFICIENCY = "efficiency"      # Speed of execution
    SAFETY = "safety"              # Content safety
    COMPLETENESS = "completeness"  # Completeness of answer


@dataclass
class PromptVariable:
    """A variable placeholder in a prompt."""
    
    name: str
    description: str
    required: bool = True
    default: Optional[str] = None
    validation: Optional[Callable[[str], bool]] = None
    
    def validate(self, value: str) -> bool:
        """Validate variable value."""
        if self.validation:
            return self.validation(value)
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "default": self.default
        }


@dataclass
class PromptTemplate:
    """A reusable prompt template with variables."""
    
    name: str
    content: str
    description: str
    tier: PromptTier
    variables: List[PromptVariable] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def render(self, **kwargs) -> str:
        """Render template with variable values."""
        rendered = self.content
        
        for var in self.variables:
            placeholder = f"{{{{{var.name}}}}}"
            
            if var.name in kwargs:
                value = kwargs[var.name]
                if not var.validate(value):
                    raise ValueError(f"Invalid value for {var.name}: {value}")
                rendered = rendered.replace(placeholder, value)
            elif var.default:
                rendered = rendered.replace(placeholder, var.default)
            elif var.required:
                raise ValueError(f"Missing required variable: {var.name}")
        
        return rendered
    
    def get_variables(self) -> List[str]:
        """Get list of variable names."""
        return [v.name for v in self.variables]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "content": self.content,
            "description": self.description,
            "tier": self.tier.value,
            "variables": [v.to_dict() for v in self.variables],
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class PromptVersion:
    """A version of a prompt."""
    
    prompt_id: str
    version: int
    content: str
    created_at: datetime = field(default_factory=datetime.now)
    author: str = "system"
    message: str = ""
    hash: str = field(default="")
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Generate hash after initialization."""
        if not self.hash:
            content_str = json.dumps({
                "prompt_id": self.prompt_id,
                "content": self.content,
                "version": self.version
            }, sort_keys=True)
            self.hash = hashlib.sha256(content_str.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "author": self.author,
            "message": self.message,
            "hash": self.hash,
            "metadata": self.metadata
        }


@dataclass
class ABTestConfig:
    """Configuration for A/B testing prompts."""
    
    test_id: str
    name: str
    prompt_a_id: str
    prompt_b_id: str
    created_at: datetime = field(default_factory=datetime.now)
    active: bool = True
    split_ratio: float = 0.5  # 0-1, portion for variant A
    target_metric: EvaluationMetric = EvaluationMetric.ACCURACY
    minimum_samples: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_id": self.test_id,
            "name": self.name,
            "prompt_a_id": self.prompt_a_id,
            "prompt_b_id": self.prompt_b_id,
            "created_at": self.created_at.isoformat(),
            "active": self.active,
            "split_ratio": self.split_ratio,
            "target_metric": self.target_metric.value,
            "minimum_samples": self.minimum_samples,
            "metadata": self.metadata
        }


@dataclass
class EvaluationResult:
    """Result of evaluating a prompt."""
    
    prompt_id: str
    version: int
    metric: EvaluationMetric
    score: float  # 0-1
    sample_size: int = 1
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt_id": self.prompt_id,
            "version": self.version,
            "metric": self.metric.value,
            "score": self.score,
            "sample_size": self.sample_size,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details
        }


class PromptManager:
    """Manages prompts with versioning, A/B testing, and evaluation."""
    
    def __init__(self):
        """Initialize prompt manager."""
        self.prompts: Dict[str, Dict[str, Any]] = {}
        self.versions: Dict[str, List[PromptVersion]] = {}
        self.templates: Dict[str, PromptTemplate] = {}
        self.ab_tests: Dict[str, ABTestConfig] = {}
        self.evaluations: Dict[str, List[EvaluationResult]] = {}
    
    def create_prompt(self, prompt_id: str, content: str,
                     tier: PromptTier = PromptTier.STANDARD,
                     description: str = "",
                     tags: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new prompt.
        
        Args:
            prompt_id: Unique prompt identifier
            content: Prompt text
            tier: Prompt tier/complexity
            description: Prompt description
            tags: Tags for categorization
            metadata: Additional metadata
        
        Returns:
            Prompt ID
        """
        if prompt_id in self.prompts:
            raise ValueError(f"Prompt {prompt_id} already exists")
        
        self.prompts[prompt_id] = {
            "content": content,
            "tier": tier,
            "description": description,
            "tags": tags or [],
            "metadata": metadata or {},
            "created_at": datetime.now(),
            "current_version": 1
        }
        
        # Create initial version
        version = PromptVersion(
            prompt_id=prompt_id,
            version=1,
            content=content,
            author="system"
        )
        self.versions[prompt_id] = [version]
        self.evaluations[prompt_id] = []
        
        return prompt_id
    
    def update_prompt(self, prompt_id: str, content: str,
                     author: str = "system",
                     message: str = "") -> PromptVersion:
        """Update prompt with new version.
        
        Args:
            prompt_id: Prompt ID
            content: New prompt content
            author: Author of change
            message: Commit message
        
        Returns:
            New PromptVersion
        """
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt {prompt_id} not found")
        
        prompt = self.prompts[prompt_id]
        current_version = prompt["current_version"]
        new_version = current_version + 1
        
        version = PromptVersion(
            prompt_id=prompt_id,
            version=new_version,
            content=content,
            author=author,
            message=message
        )
        
        self.versions[prompt_id].append(version)
        prompt["current_version"] = new_version
        prompt["content"] = content
        
        return version
    
    def get_prompt(self, prompt_id: str, version: Optional[int] = None) -> str:
        """Get prompt content.
        
        Args:
            prompt_id: Prompt ID
            version: Specific version (None = latest)
        
        Returns:
            Prompt content
        """
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt {prompt_id} not found")
        
        if version is None:
            return self.prompts[prompt_id]["content"]
        
        versions = self.versions[prompt_id]
        for v in versions:
            if v.version == version:
                return v.content
        
        raise ValueError(f"Version {version} not found for prompt {prompt_id}")
    
    def get_version_history(self, prompt_id: str) -> List[PromptVersion]:
        """Get all versions of a prompt.
        
        Args:
            prompt_id: Prompt ID
        
        Returns:
            List of PromptVersion objects
        """
        if prompt_id not in self.versions:
            raise ValueError(f"Prompt {prompt_id} not found")
        
        return self.versions[prompt_id]
    
    def list_prompts(self, tier: Optional[PromptTier] = None,
                    tags: Optional[List[str]] = None) -> List[str]:
        """List prompts by tier or tags.
        
        Args:
            tier: Filter by tier
            tags: Filter by tags (all must match)
        
        Returns:
            List of prompt IDs
        """
        results = []
        
        for prompt_id, prompt in self.prompts.items():
            if tier and prompt["tier"] != tier:
                continue
            
            if tags:
                if not all(tag in prompt["tags"] for tag in tags):
                    continue
            
            results.append(prompt_id)
        
        return results
    
    def create_template(self, template_name: str, content: str,
                       description: str,
                       tier: PromptTier = PromptTier.STANDARD,
                       variables: Optional[List[PromptVariable]] = None,
                       tags: Optional[List[str]] = None) -> PromptTemplate:
        """Create a reusable prompt template.
        
        Args:
            template_name: Template name
            content: Template content with {{variable}} placeholders
            description: Template description
            tier: Template tier
            variables: Variable definitions
            tags: Template tags
        
        Returns:
            PromptTemplate object
        """
        template = PromptTemplate(
            name=template_name,
            content=content,
            description=description,
            tier=tier,
            variables=variables or [],
            tags=tags or []
        )
        
        self.templates[template_name] = template
        return template
    
    def render_template(self, template_name: str, **kwargs) -> str:
        """Render a template with variable values.
        
        Args:
            template_name: Template name
            **kwargs: Variable values
        
        Returns:
            Rendered prompt text
        """
        if template_name not in self.templates:
            raise ValueError(f"Template {template_name} not found")
        
        return self.templates[template_name].render(**kwargs)
    
    def create_ab_test(self, test_id: str, test_name: str,
                      prompt_a_id: str, prompt_b_id: str,
                      split_ratio: float = 0.5,
                      target_metric: EvaluationMetric = EvaluationMetric.ACCURACY,
                      metadata: Optional[Dict[str, Any]] = None) -> ABTestConfig:
        """Create an A/B test.
        
        Args:
            test_id: Test ID
            test_name: Test name
            prompt_a_id: Prompt A ID
            prompt_b_id: Prompt B ID
            split_ratio: Portion of traffic for A (0-1)
            target_metric: Metric to optimize for
            metadata: Additional metadata
        
        Returns:
            ABTestConfig object
        """
        if prompt_a_id not in self.prompts:
            raise ValueError(f"Prompt {prompt_a_id} not found")
        if prompt_b_id not in self.prompts:
            raise ValueError(f"Prompt {prompt_b_id} not found")
        
        test = ABTestConfig(
            test_id=test_id,
            name=test_name,
            prompt_a_id=prompt_a_id,
            prompt_b_id=prompt_b_id,
            split_ratio=split_ratio,
            target_metric=target_metric,
            metadata=metadata or {}
        )
        
        self.ab_tests[test_id] = test
        return test
    
    def get_ab_test(self, test_id: str) -> ABTestConfig:
        """Get A/B test configuration.
        
        Args:
            test_id: Test ID
        
        Returns:
            ABTestConfig object
        """
        if test_id not in self.ab_tests:
            raise ValueError(f"A/B test {test_id} not found")
        
        return self.ab_tests[test_id]
    
    def record_evaluation(self, prompt_id: str, version: int,
                         metric: EvaluationMetric, score: float,
                         sample_size: int = 1,
                         details: Optional[Dict[str, Any]] = None) -> EvaluationResult:
        """Record evaluation result for a prompt.
        
        Args:
            prompt_id: Prompt ID
            version: Prompt version
            metric: Evaluation metric
            score: Score (0-1)
            sample_size: Sample size for evaluation
            details: Additional details
        
        Returns:
            EvaluationResult object
        """
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt {prompt_id} not found")
        
        if not 0 <= score <= 1:
            raise ValueError(f"Score must be between 0 and 1, got {score}")
        
        result = EvaluationResult(
            prompt_id=prompt_id,
            version=version,
            metric=metric,
            score=score,
            sample_size=sample_size,
            details=details or {}
        )
        
        self.evaluations[prompt_id].append(result)
        return result
    
    def get_evaluation_history(self, prompt_id: str,
                              metric: Optional[EvaluationMetric] = None) -> List[EvaluationResult]:
        """Get evaluation history for a prompt.
        
        Args:
            prompt_id: Prompt ID
            metric: Filter by metric (None = all)
        
        Returns:
            List of EvaluationResult objects
        """
        if prompt_id not in self.evaluations:
            return []
        
        results = self.evaluations[prompt_id]
        
        if metric:
            results = [r for r in results if r.metric == metric]
        
        return results
    
    def get_best_version(self, prompt_id: str,
                        metric: EvaluationMetric = EvaluationMetric.ACCURACY) -> Optional[int]:
        """Get best performing version by metric.
        
        Args:
            prompt_id: Prompt ID
            metric: Evaluation metric
        
        Returns:
            Best version number (None if no evaluations)
        """
        history = self.get_evaluation_history(prompt_id, metric)
        
        if not history:
            return None
        
        # Group by version
        by_version = {}
        for result in history:
            version = result.version
            if version not in by_version:
                by_version[version] = []
            by_version[version].append(result.score)
        
        # Calculate average per version
        best_version = None
        best_score = -1
        
        for version, scores in by_version.items():
            avg_score = sum(scores) / len(scores)
            if avg_score > best_score:
                best_score = avg_score
                best_version = version
        
        return best_version
    
    def compare_versions(self, prompt_id: str, version1: int, version2: int,
                        metric: EvaluationMetric = EvaluationMetric.ACCURACY) -> Dict[str, Any]:
        """Compare two versions of a prompt.
        
        Args:
            prompt_id: Prompt ID
            version1: First version
            version2: Second version
            metric: Evaluation metric
        
        Returns:
            Comparison dictionary
        """
        history = self.get_evaluation_history(prompt_id, metric)
        
        results1 = [r for r in history if r.version == version1]
        results2 = [r for r in history if r.version == version2]
        
        avg1 = sum(r.score for r in results1) / len(results1) if results1 else None
        avg2 = sum(r.score for r in results2) / len(results2) if results2 else None
        
        return {
            "version1": version1,
            "version2": version2,
            "metric": metric.value,
            "avg_score_v1": avg1,
            "avg_score_v2": avg2,
            "samples_v1": len(results1),
            "samples_v2": len(results2),
            "improvement": (avg2 - avg1) if (avg1 and avg2) else None
        }
    
    def export_prompt(self, prompt_id: str, version: Optional[int] = None) -> Dict[str, Any]:
        """Export prompt configuration.
        
        Args:
            prompt_id: Prompt ID
            version: Specific version (None = latest)
        
        Returns:
            Prompt configuration dict
        """
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt {prompt_id} not found")
        
        prompt = self.prompts[prompt_id]
        
        return {
            "prompt_id": prompt_id,
            "content": self.get_prompt(prompt_id, version),
            "tier": prompt["tier"].value,
            "description": prompt["description"],
            "tags": prompt["tags"],
            "metadata": prompt["metadata"],
            "version": version or prompt["current_version"]
        }
