"""Tests for prompt management system."""

import pytest
from agent_sdk.prompt_management import (
    PromptManager, PromptTier, PromptTemplate, PromptVariable,
    PromptVersion, ABTestConfig, EvaluationResult, EvaluationMetric
)


class TestPromptVariable:
    """Tests for PromptVariable."""
    
    def test_creation(self):
        """Test variable creation."""
        var = PromptVariable(
            name="topic",
            description="Topic to summarize",
            required=True
        )
        
        assert var.name == "topic"
        assert var.required is True
    
    def test_validation(self):
        """Test variable validation."""
        var = PromptVariable(
            name="count",
            description="Number",
            validation=lambda x: x.isdigit()
        )
        
        assert var.validate("123") is True
        assert var.validate("abc") is False
    
    def test_to_dict(self):
        """Test serialization."""
        var = PromptVariable(
            name="test",
            description="Test var",
            default="value"
        )
        
        d = var.to_dict()
        
        assert d["name"] == "test"
        assert d["default"] == "value"


class TestPromptTemplate:
    """Tests for PromptTemplate."""
    
    def test_creation(self):
        """Test template creation."""
        template = PromptTemplate(
            name="summarize",
            content="Summarize {{topic}} in {{length}} sentences",
            description="Summarization template",
            tier=PromptTier.STANDARD
        )
        
        assert template.name == "summarize"
        assert "topic" in template.content
    
    def test_render_basic(self):
        """Test basic template rendering."""
        template = PromptTemplate(
            name="test",
            content="Hello {{name}}!",
            description="Greeting",
            tier=PromptTier.SIMPLE,
            variables=[
                PromptVariable("name", "Person's name")
            ]
        )
        
        rendered = template.render(name="Alice")
        
        assert rendered == "Hello Alice!"
    
    def test_render_multiple_vars(self):
        """Test rendering with multiple variables."""
        template = PromptTemplate(
            name="compose",
            content="Write a {{type}} about {{topic}} in {{style}}",
            description="Composition template",
            tier=PromptTier.STANDARD,
            variables=[
                PromptVariable("type", "Content type"),
                PromptVariable("topic", "Topic"),
                PromptVariable("style", "Writing style")
            ]
        )
        
        rendered = template.render(
            type="essay",
            topic="AI",
            style="academic"
        )
        
        assert rendered == "Write a essay about AI in academic"
    
    def test_render_missing_required(self):
        """Test rendering with missing required variable."""
        template = PromptTemplate(
            name="test",
            content="Hello {{name}}!",
            description="Test",
            tier=PromptTier.SIMPLE,
            variables=[
                PromptVariable("name", "Name", required=True)
            ]
        )
        
        with pytest.raises(ValueError):
            template.render()
    
    def test_render_default_value(self):
        """Test rendering with default variable value."""
        template = PromptTemplate(
            name="test",
            content="Hello {{name}}!",
            description="Test",
            tier=PromptTier.SIMPLE,
            variables=[
                PromptVariable("name", "Name", default="Anonymous")
            ]
        )
        
        rendered = template.render()
        
        assert rendered == "Hello Anonymous!"
    
    def test_get_variables(self):
        """Test getting variable names."""
        template = PromptTemplate(
            name="test",
            content="About {{topic}} in {{style}}",
            description="Test",
            tier=PromptTier.SIMPLE,
            variables=[
                PromptVariable("topic", "Topic"),
                PromptVariable("style", "Style")
            ]
        )
        
        vars = template.get_variables()
        
        assert len(vars) == 2
        assert "topic" in vars


class TestPromptVersion:
    """Tests for PromptVersion."""
    
    def test_creation(self):
        """Test version creation."""
        version = PromptVersion(
            prompt_id="test",
            version=1,
            content="Test prompt"
        )
        
        assert version.prompt_id == "test"
        assert version.version == 1
    
    def test_hash_generation(self):
        """Test hash generation."""
        v1 = PromptVersion(
            prompt_id="test",
            version=1,
            content="Content A"
        )
        
        v2 = PromptVersion(
            prompt_id="test",
            version=2,
            content="Content B"
        )
        
        assert v1.hash != v2.hash
    
    def test_to_dict(self):
        """Test serialization."""
        version = PromptVersion(
            prompt_id="test",
            version=1,
            content="Content",
            author="alice"
        )
        
        d = version.to_dict()
        
        assert d["prompt_id"] == "test"
        assert d["author"] == "alice"


class TestABTestConfig:
    """Tests for ABTestConfig."""
    
    def test_creation(self):
        """Test A/B test creation."""
        config = ABTestConfig(
            test_id="test1",
            name="Test 1",
            prompt_a_id="promptA",
            prompt_b_id="promptB"
        )
        
        assert config.test_id == "test1"
        assert config.split_ratio == 0.5
    
    def test_to_dict(self):
        """Test serialization."""
        config = ABTestConfig(
            test_id="test1",
            name="Test",
            prompt_a_id="A",
            prompt_b_id="B",
            split_ratio=0.6
        )
        
        d = config.to_dict()
        
        assert d["split_ratio"] == 0.6


class TestEvaluationResult:
    """Tests for EvaluationResult."""
    
    def test_creation(self):
        """Test result creation."""
        result = EvaluationResult(
            prompt_id="test",
            version=1,
            metric=EvaluationMetric.ACCURACY,
            score=0.85
        )
        
        assert result.prompt_id == "test"
        assert result.score == 0.85
    
    def test_to_dict(self):
        """Test serialization."""
        result = EvaluationResult(
            prompt_id="test",
            version=1,
            metric=EvaluationMetric.CLARITY,
            score=0.9
        )
        
        d = result.to_dict()
        
        assert d["metric"] == "clarity"
        assert d["score"] == 0.9


class TestPromptManager:
    """Tests for PromptManager."""
    
    def test_initialization(self):
        """Test manager initialization."""
        manager = PromptManager()
        
        assert manager.prompts == {}
        assert manager.versions == {}
        assert manager.templates == {}
    
    def test_create_prompt(self):
        """Test creating a prompt."""
        manager = PromptManager()
        
        prompt_id = manager.create_prompt(
            "test",
            "Test prompt content",
            tier=PromptTier.STANDARD
        )
        
        assert prompt_id == "test"
        assert "test" in manager.prompts
        assert manager.prompts["test"]["content"] == "Test prompt content"
    
    def test_create_duplicate_prompt(self):
        """Test creating duplicate prompt raises error."""
        manager = PromptManager()
        
        manager.create_prompt("test", "Content")
        
        with pytest.raises(ValueError):
            manager.create_prompt("test", "Different content")
    
    def test_update_prompt(self):
        """Test updating a prompt."""
        manager = PromptManager()
        manager.create_prompt("test", "Original content")
        
        version = manager.update_prompt("test", "Updated content", author="alice")
        
        assert version.version == 2
        assert version.author == "alice"
        assert manager.get_prompt("test") == "Updated content"
    
    def test_get_prompt_latest(self):
        """Test getting latest prompt version."""
        manager = PromptManager()
        manager.create_prompt("test", "Version 1")
        manager.update_prompt("test", "Version 2")
        
        content = manager.get_prompt("test")
        
        assert content == "Version 2"
    
    def test_get_prompt_specific_version(self):
        """Test getting specific prompt version."""
        manager = PromptManager()
        manager.create_prompt("test", "Version 1")
        manager.update_prompt("test", "Version 2")
        
        content = manager.get_prompt("test", version=1)
        
        assert content == "Version 1"
    
    def test_get_version_history(self):
        """Test getting version history."""
        manager = PromptManager()
        manager.create_prompt("test", "V1")
        manager.update_prompt("test", "V2")
        manager.update_prompt("test", "V3")
        
        history = manager.get_version_history("test")
        
        assert len(history) == 3
        assert history[0].version == 1
        assert history[2].version == 3
    
    def test_list_prompts_all(self):
        """Test listing all prompts."""
        manager = PromptManager()
        manager.create_prompt("p1", "Content 1")
        manager.create_prompt("p2", "Content 2")
        manager.create_prompt("p3", "Content 3")
        
        prompts = manager.list_prompts()
        
        assert len(prompts) == 3
    
    def test_list_prompts_by_tier(self):
        """Test listing prompts by tier."""
        manager = PromptManager()
        manager.create_prompt("simple", "Content", tier=PromptTier.SIMPLE)
        manager.create_prompt("standard", "Content", tier=PromptTier.STANDARD)
        
        prompts = manager.list_prompts(tier=PromptTier.SIMPLE)
        
        assert len(prompts) == 1
        assert prompts[0] == "simple"
    
    def test_list_prompts_by_tags(self):
        """Test listing prompts by tags."""
        manager = PromptManager()
        manager.create_prompt("p1", "Content", tags=["qa", "test"])
        manager.create_prompt("p2", "Content", tags=["summarize"])
        
        prompts = manager.list_prompts(tags=["qa"])
        
        assert len(prompts) == 1
    
    def test_create_template(self):
        """Test creating a template."""
        manager = PromptManager()
        
        template = manager.create_template(
            "summarize",
            "Summarize {{text}} in {{length}} words",
            "Summarization template",
            variables=[
                PromptVariable("text", "Text to summarize"),
                PromptVariable("length", "Output length")
            ]
        )
        
        assert template.name == "summarize"
        assert len(template.variables) == 2
    
    def test_render_template(self):
        """Test rendering a template."""
        manager = PromptManager()
        
        manager.create_template(
            "greet",
            "Hello {{name}}, welcome to {{place}}!",
            "Greeting template",
            variables=[
                PromptVariable("name", "Name"),
                PromptVariable("place", "Place")
            ]
        )
        
        rendered = manager.render_template(
            "greet",
            name="Alice",
            place="Wonderland"
        )
        
        assert rendered == "Hello Alice, welcome to Wonderland!"
    
    def test_create_ab_test(self):
        """Test creating A/B test."""
        manager = PromptManager()
        manager.create_prompt("a", "Prompt A")
        manager.create_prompt("b", "Prompt B")
        
        test = manager.create_ab_test(
            "test1",
            "Test 1",
            "a",
            "b",
            split_ratio=0.6
        )
        
        assert test.test_id == "test1"
        assert test.split_ratio == 0.6
    
    def test_get_ab_test(self):
        """Test getting A/B test."""
        manager = PromptManager()
        manager.create_prompt("a", "A")
        manager.create_prompt("b", "B")
        manager.create_ab_test("test1", "Test", "a", "b")
        
        test = manager.get_ab_test("test1")
        
        assert test.test_id == "test1"
    
    def test_record_evaluation(self):
        """Test recording evaluation."""
        manager = PromptManager()
        manager.create_prompt("test", "Content")
        
        result = manager.record_evaluation(
            "test",
            version=1,
            metric=EvaluationMetric.ACCURACY,
            score=0.85,
            sample_size=50
        )
        
        assert result.score == 0.85
        assert result.sample_size == 50
    
    def test_record_invalid_score(self):
        """Test recording invalid score."""
        manager = PromptManager()
        manager.create_prompt("test", "Content")
        
        with pytest.raises(ValueError):
            manager.record_evaluation(
                "test",
                version=1,
                metric=EvaluationMetric.ACCURACY,
                score=1.5
            )
    
    def test_get_evaluation_history(self):
        """Test getting evaluation history."""
        manager = PromptManager()
        manager.create_prompt("test", "Content")
        
        manager.record_evaluation("test", 1, EvaluationMetric.ACCURACY, 0.85)
        manager.record_evaluation("test", 1, EvaluationMetric.CLARITY, 0.90)
        manager.record_evaluation("test", 1, EvaluationMetric.ACCURACY, 0.88)
        
        history = manager.get_evaluation_history("test", EvaluationMetric.ACCURACY)
        
        assert len(history) == 2
    
    def test_get_best_version(self):
        """Test getting best version by metric."""
        manager = PromptManager()
        manager.create_prompt("test", "V1")
        manager.update_prompt("test", "V2")
        manager.update_prompt("test", "V3")
        
        manager.record_evaluation("test", 1, EvaluationMetric.ACCURACY, 0.80)
        manager.record_evaluation("test", 2, EvaluationMetric.ACCURACY, 0.85)
        manager.record_evaluation("test", 3, EvaluationMetric.ACCURACY, 0.83)
        
        best = manager.get_best_version("test", EvaluationMetric.ACCURACY)
        
        assert best == 2
    
    def test_compare_versions(self):
        """Test comparing two versions."""
        manager = PromptManager()
        manager.create_prompt("test", "V1")
        manager.update_prompt("test", "V2")
        
        manager.record_evaluation("test", 1, EvaluationMetric.ACCURACY, 0.80)
        manager.record_evaluation("test", 2, EvaluationMetric.ACCURACY, 0.90)
        
        comparison = manager.compare_versions(
            "test",
            1,
            2,
            EvaluationMetric.ACCURACY
        )
        
        assert comparison["avg_score_v1"] == 0.80
        assert comparison["avg_score_v2"] == 0.90
        assert abs(comparison["improvement"] - 0.10) < 0.0001
    
    def test_export_prompt(self):
        """Test exporting prompt."""
        manager = PromptManager()
        manager.create_prompt(
            "test",
            "Content",
            tier=PromptTier.ADVANCED,
            description="Test prompt",
            tags=["test"]
        )
        
        exported = manager.export_prompt("test")
        
        assert exported["prompt_id"] == "test"
        assert exported["tier"] == "advanced"
        assert "test" in exported["tags"]


class TestPromptTierEnum:
    """Tests for PromptTier enum."""
    
    def test_tier_values(self):
        """Test tier values."""
        assert PromptTier.SIMPLE.value == "simple"
        assert PromptTier.STANDARD.value == "standard"
        assert PromptTier.ADVANCED.value == "advanced"
        assert PromptTier.EXPERT.value == "expert"


class TestEvaluationMetricEnum:
    """Tests for EvaluationMetric enum."""
    
    def test_metric_values(self):
        """Test metric values."""
        assert EvaluationMetric.ACCURACY.value == "accuracy"
        assert EvaluationMetric.RELEVANCE.value == "relevance"
        assert EvaluationMetric.COHERENCE.value == "coherence"
        assert EvaluationMetric.CLARITY.value == "clarity"
        assert EvaluationMetric.EFFICIENCY.value == "efficiency"
        assert EvaluationMetric.SAFETY.value == "safety"
