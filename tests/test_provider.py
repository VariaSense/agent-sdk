"""Tests for LLM provider infrastructure."""

import pytest
from agent_sdk.llm.provider import (
    ProviderType, ModelTier, ModelConfig, ModelRegistry,
    ProviderFactory, OpenAIProviderFactory, AnthropicProviderFactory,
    LocalProviderFactory, ProviderManager, create_default_registry
)


class TestModelConfig:
    """Tests for ModelConfig."""
    
    def test_creation(self):
        """Test model config creation."""
        config = ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI,
            tier=ModelTier.EXPERT,
            cost_per_1k_input=0.03,
            cost_per_1k_output=0.06
        )
        
        assert config.model_id == "gpt-4"
        assert config.provider == ProviderType.OPENAI
        assert config.tier == ModelTier.EXPERT
        assert config.cost_per_1k_input == 0.03
    
    def test_to_dict(self):
        """Test serialization."""
        config = ModelConfig(
            model_id="claude-3",
            provider=ProviderType.ANTHROPIC,
            supports_vision=True
        )
        
        d = config.to_dict()
        
        assert d["model_id"] == "claude-3"
        assert d["provider"] == "anthropic"
        assert d["supports_vision"] is True


class TestModelRegistry:
    """Tests for ModelRegistry."""
    
    def test_register_model(self):
        """Test registering a model."""
        registry = ModelRegistry()
        config = ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI
        )
        
        registry.register_model(config)
        
        assert "gpt-4" in registry.models
        assert registry.default_model == "gpt-4"
    
    def test_get_model(self):
        """Test retrieving model."""
        registry = ModelRegistry()
        config = ModelConfig(model_id="gpt-4", provider=ProviderType.OPENAI)
        registry.register_model(config)
        
        retrieved = registry.get_model("gpt-4")
        
        assert retrieved.model_id == "gpt-4"
    
    def test_get_nonexistent_model(self):
        """Test getting non-existent model."""
        registry = ModelRegistry()
        
        model = registry.get_model("nonexistent")
        
        assert model is None
    
    def test_list_models(self):
        """Test listing models."""
        registry = ModelRegistry()
        registry.register_model(ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI,
            tier=ModelTier.EXPERT
        ))
        registry.register_model(ModelConfig(
            model_id="gpt-3.5",
            provider=ProviderType.OPENAI,
            tier=ModelTier.FAST
        ))
        
        models = registry.list_models()
        
        assert len(models) == 2
    
    def test_list_models_by_provider(self):
        """Test filtering models by provider."""
        registry = ModelRegistry()
        registry.register_model(ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI
        ))
        registry.register_model(ModelConfig(
            model_id="claude-3",
            provider=ProviderType.ANTHROPIC
        ))
        
        openai_models = registry.list_models(provider=ProviderType.OPENAI)
        
        assert len(openai_models) == 1
        assert openai_models[0].model_id == "gpt-4"
    
    def test_list_models_by_tier(self):
        """Test filtering models by tier."""
        registry = ModelRegistry()
        registry.register_model(ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI,
            tier=ModelTier.EXPERT
        ))
        registry.register_model(ModelConfig(
            model_id="gpt-3.5",
            provider=ProviderType.OPENAI,
            tier=ModelTier.FAST
        ))
        
        fast_models = registry.list_models(tier=ModelTier.FAST)
        
        assert len(fast_models) == 1
        assert fast_models[0].model_id == "gpt-3.5"
    
    def test_get_fastest_model(self):
        """Test getting fastest model."""
        registry = ModelRegistry()
        registry.register_model(ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI,
            tier=ModelTier.FAST,
            cost_per_1k_output=0.01
        ))
        registry.register_model(ModelConfig(
            model_id="gpt-3.5",
            provider=ProviderType.OPENAI,
            tier=ModelTier.FAST,
            cost_per_1k_output=0.001
        ))
        
        fastest = registry.get_fastest_model()
        
        assert fastest.model_id == "gpt-3.5"
    
    def test_get_most_capable_model(self):
        """Test getting most capable model."""
        registry = ModelRegistry()
        registry.register_model(ModelConfig(
            model_id="gpt-3.5",
            provider=ProviderType.OPENAI,
            tier=ModelTier.FAST
        ))
        registry.register_model(ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI,
            tier=ModelTier.EXPERT
        ))
        
        capable = registry.get_most_capable_model()
        
        assert capable.model_id == "gpt-4"


class TestProviderFactory:
    """Tests for provider factories."""
    
    def test_openai_factory_creation(self):
        """Test OpenAI factory."""
        factory = OpenAIProviderFactory(api_key="test-key")
        
        assert factory.api_key == "test-key"
        assert factory.validate_credentials() is True
    
    def test_openai_factory_no_credentials(self):
        """Test OpenAI factory without credentials."""
        factory = OpenAIProviderFactory()
        
        assert factory.validate_credentials() is False
    
    def test_openai_factory_create_client(self):
        """Test creating OpenAI client."""
        factory = OpenAIProviderFactory(api_key="test-key")
        config = ModelConfig(model_id="gpt-4", provider=ProviderType.OPENAI)
        
        client = factory.create_client(config)
        
        assert client["provider"] == "openai"
        assert client["model"] == "gpt-4"
    
    def test_anthropic_factory_creation(self):
        """Test Anthropic factory."""
        factory = AnthropicProviderFactory(api_key="test-key")
        
        assert factory.validate_credentials() is True
    
    def test_local_factory_creation(self):
        """Test local model factory."""
        factory = LocalProviderFactory(model_path="/models/llama2")
        
        assert factory.validate_credentials() is True
        assert factory.model_path == "/models/llama2"


class TestProviderManager:
    """Tests for ProviderManager."""
    
    def test_initialization(self):
        """Test manager initialization."""
        manager = ProviderManager()
        
        assert ProviderType.OPENAI in manager.providers
        assert ProviderType.ANTHROPIC in manager.providers
        assert ProviderType.LOCAL in manager.providers
    
    def test_register_model(self):
        """Test registering model."""
        manager = ProviderManager()
        config = ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI
        )
        
        manager.register_model(config)
        
        assert manager.get_model("gpt-4") is not None
    
    def test_get_model(self):
        """Test getting model."""
        manager = ProviderManager()
        config = ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI
        )
        manager.register_model(config)
        
        retrieved = manager.get_model("gpt-4")
        
        assert retrieved.model_id == "gpt-4"
    
    def test_get_client(self):
        """Test getting client for model."""
        manager = ProviderManager()
        config = ModelConfig(
            model_id="gpt-4",
            provider=ProviderType.OPENAI
        )
        manager.register_model(config)
        manager.register_provider(ProviderType.OPENAI, OpenAIProviderFactory(api_key="test"))
        
        client = manager.get_client("gpt-4")
        
        assert client["provider"] == "openai"
    
    def test_get_nonexistent_model(self):
        """Test getting non-existent model raises error."""
        manager = ProviderManager()
        
        with pytest.raises(ValueError):
            manager.get_client("nonexistent")
    
    def test_list_models(self):
        """Test listing models."""
        manager = ProviderManager()
        config1 = ModelConfig(model_id="gpt-4", provider=ProviderType.OPENAI)
        config2 = ModelConfig(model_id="claude-3", provider=ProviderType.ANTHROPIC)
        
        manager.register_model(config1)
        manager.register_model(config2)
        
        models = manager.list_models()
        
        assert len(models) == 2


class TestDefaultRegistry:
    """Tests for default registry."""
    
    def test_create_default_registry(self):
        """Test creating default registry."""
        registry = create_default_registry()
        
        # Check OpenAI models
        gpt4 = registry.get_model("gpt-4")
        assert gpt4 is not None
        assert gpt4.provider == ProviderType.OPENAI
        assert gpt4.tier == ModelTier.EXPERT
        
        gpt35 = registry.get_model("gpt-3.5-turbo")
        assert gpt35 is not None
        assert gpt35.tier == ModelTier.FAST
        
        # Check Anthropic models
        claude = registry.get_model("claude-3-opus")
        assert claude is not None
        assert claude.provider == ProviderType.ANTHROPIC
        assert claude.tier == ModelTier.EXPERT
    
    def test_default_registry_capabilities(self):
        """Test model capabilities in default registry."""
        registry = create_default_registry()
        
        gpt4 = registry.get_model("gpt-4")
        assert "vision" in gpt4.capabilities
        
        claude = registry.get_model("claude-3-opus")
        assert "reasoning" in claude.capabilities
    
    def test_default_registry_costs(self):
        """Test pricing in default registry."""
        registry = create_default_registry()
        
        gpt4 = registry.get_model("gpt-4")
        assert gpt4.cost_per_1k_input > 0
        assert gpt4.cost_per_1k_output > gpt4.cost_per_1k_input
        
        gpt35 = registry.get_model("gpt-3.5-turbo")
        assert gpt35.cost_per_1k_input < gpt4.cost_per_1k_input


class TestProviderTypeEnum:
    """Tests for ProviderType enum."""
    
    def test_provider_types(self):
        """Test provider type values."""
        assert ProviderType.OPENAI.value == "openai"
        assert ProviderType.ANTHROPIC.value == "anthropic"
        assert ProviderType.HUGGINGFACE.value == "huggingface"
        assert ProviderType.LOCAL.value == "local"
        assert ProviderType.AZURE.value == "azure"


class TestModelTierEnum:
    """Tests for ModelTier enum."""
    
    def test_model_tiers(self):
        """Test model tier values."""
        assert ModelTier.FAST.value == "fast"
        assert ModelTier.BALANCED.value == "balanced"
        assert ModelTier.CAPABLE.value == "capable"
        assert ModelTier.EXPERT.value == "expert"
