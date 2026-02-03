"""LLM provider abstraction and factory."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type
from enum import Enum
from abc import ABC, abstractmethod


class ProviderType(Enum):
    """Supported LLM providers."""
    
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    AZURE = "azure"
    CUSTOM = "custom"


class ModelTier(Enum):
    """Model capability tiers."""
    
    FAST = "fast"              # Fast, cheap, limited reasoning
    BALANCED = "balanced"       # Good balance of speed and capability
    CAPABLE = "capable"         # Advanced reasoning, slower
    EXPERT = "expert"          # Best in class, most expensive


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    
    model_id: str                           # e.g., "gpt-4", "claude-3-opus"
    provider: ProviderType
    tier: ModelTier = ModelTier.BALANCED
    
    # Performance characteristics
    max_tokens: int = 4096
    context_window: int = 8192
    request_timeout_ms: float = 30000.0
    
    # Pricing (per 1K tokens)
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    
    # Capabilities
    supports_function_calling: bool = True
    supports_streaming: bool = True
    supports_vision: bool = False
    
    # Defaults
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    
    # Metadata
    capabilities: list = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "provider": self.provider.value,
            "tier": self.tier.value,
            "max_tokens": self.max_tokens,
            "context_window": self.context_window,
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
            "supports_function_calling": self.supports_function_calling,
            "supports_streaming": self.supports_streaming,
            "supports_vision": self.supports_vision,
            "capabilities": self.capabilities,
            "metadata": self.metadata
        }


@dataclass
class ModelRegistry:
    """Registry of available models."""
    
    models: Dict[str, ModelConfig] = field(default_factory=dict)
    default_model: Optional[str] = None
    
    def register_model(self, config: ModelConfig) -> None:
        """Register a model configuration.
        
        Args:
            config: Model configuration
        """
        self.models[config.model_id] = config
        if self.default_model is None:
            self.default_model = config.model_id
    
    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get model configuration.
        
        Args:
            model_id: Model identifier
        
        Returns:
            Configuration or None
        """
        return self.models.get(model_id)
    
    def list_models(self, provider: Optional[ProviderType] = None,
                   tier: Optional[ModelTier] = None) -> list[ModelConfig]:
        """List available models.
        
        Args:
            provider: Filter by provider
            tier: Filter by tier
        
        Returns:
            List of matching models
        """
        models = list(self.models.values())
        
        if provider:
            models = [m for m in models if m.provider == provider]
        
        if tier:
            models = [m for m in models if m.tier == tier]
        
        return models
    
    def get_fastest_model(self) -> Optional[ModelConfig]:
        """Get fastest/cheapest model."""
        fast_models = [m for m in self.models.values() if m.tier == ModelTier.FAST]
        if not fast_models:
            return None
        # Sort by output cost (cheapest first)
        return sorted(fast_models, key=lambda m: m.cost_per_1k_output)[0]
    
    def get_most_capable_model(self) -> Optional[ModelConfig]:
        """Get most capable model."""
        capable_models = [m for m in self.models.values() 
                         if m.tier in [ModelTier.CAPABLE, ModelTier.EXPERT]]
        if not capable_models:
            return None
        # Sort by tier (expert first), then cost
        return sorted(capable_models, 
                     key=lambda m: (m.tier != ModelTier.EXPERT, m.cost_per_1k_output))[0]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "models": {mid: cfg.to_dict() for mid, cfg in self.models.items()},
            "default_model": self.default_model
        }


class ProviderFactory(ABC):
    """Base class for provider factories."""
    
    @abstractmethod
    def create_client(self, model_config: ModelConfig) -> Any:
        """Create client for model.
        
        Args:
            model_config: Model configuration
        
        Returns:
            Provider-specific client
        """
        pass
    
    @abstractmethod
    def validate_credentials(self) -> bool:
        """Validate provider credentials."""
        pass


class OpenAIProviderFactory(ProviderFactory):
    """OpenAI provider factory."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize factory.
        
        Args:
            api_key: OpenAI API key
        """
        self.api_key = api_key
    
    def create_client(self, model_config: ModelConfig) -> Any:
        """Create OpenAI client."""
        # In real implementation, would return OpenAI client
        return {"provider": "openai", "model": model_config.model_id}
    
    def validate_credentials(self) -> bool:
        """Check if API key is set."""
        return bool(self.api_key)


class AnthropicProviderFactory(ProviderFactory):
    """Anthropic provider factory."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize factory.
        
        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key
    
    def create_client(self, model_config: ModelConfig) -> Any:
        """Create Anthropic client."""
        # In real implementation, would return Anthropic client
        return {"provider": "anthropic", "model": model_config.model_id}
    
    def validate_credentials(self) -> bool:
        """Check if API key is set."""
        return bool(self.api_key)


class LocalProviderFactory(ProviderFactory):
    """Local model provider factory."""
    
    def __init__(self, model_path: Optional[str] = None):
        """Initialize factory.
        
        Args:
            model_path: Path to local model
        """
        self.model_path = model_path
    
    def create_client(self, model_config: ModelConfig) -> Any:
        """Create local model client."""
        # In real implementation, would load local model
        return {"provider": "local", "model": model_config.model_id, "path": self.model_path}
    
    def validate_credentials(self) -> bool:
        """Check if model path exists."""
        return bool(self.model_path)


class ProviderManager:
    """Manages multiple LLM providers."""
    
    def __init__(self):
        """Initialize provider manager."""
        self.providers: Dict[ProviderType, ProviderFactory] = {}
        self.registry = ModelRegistry()
        self._initialize_default_providers()
    
    def _initialize_default_providers(self) -> None:
        """Initialize with default providers."""
        self.register_provider(ProviderType.OPENAI, OpenAIProviderFactory())
        self.register_provider(ProviderType.ANTHROPIC, AnthropicProviderFactory())
        self.register_provider(ProviderType.LOCAL, LocalProviderFactory())
    
    def register_provider(self, provider_type: ProviderType, 
                         factory: ProviderFactory) -> None:
        """Register a provider.
        
        Args:
            provider_type: Type of provider
            factory: Provider factory
        """
        self.providers[provider_type] = factory
    
    def register_model(self, config: ModelConfig) -> None:
        """Register a model.
        
        Args:
            config: Model configuration
        """
        self.registry.register_model(config)
    
    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get model config.
        
        Args:
            model_id: Model identifier
        
        Returns:
            Configuration or None
        """
        return self.registry.get_model(model_id)
    
    def get_client(self, model_id: str) -> Any:
        """Get client for model.
        
        Args:
            model_id: Model identifier
        
        Returns:
            Provider client
        
        Raises:
            ValueError: If model not found
        """
        config = self.registry.get_model(model_id)
        if not config:
            raise ValueError(f"Model '{model_id}' not found in registry")
        
        factory = self.providers.get(config.provider)
        if not factory:
            raise ValueError(f"Provider '{config.provider.value}' not registered")
        
        return factory.create_client(config)
    
    def list_models(self) -> list[ModelConfig]:
        """List all registered models."""
        return list(self.registry.models.values())


# Pre-configured model registry
def create_default_registry() -> ModelRegistry:
    """Create registry with common models."""
    registry = ModelRegistry()
    
    # OpenAI models
    registry.register_model(ModelConfig(
        model_id="gpt-4",
        provider=ProviderType.OPENAI,
        tier=ModelTier.EXPERT,
        max_tokens=8192,
        context_window=8192,
        cost_per_1k_input=0.03,
        cost_per_1k_output=0.06,
        supports_vision=True,
        capabilities=["reasoning", "function_calling", "vision"]
    ))
    
    registry.register_model(ModelConfig(
        model_id="gpt-4-turbo",
        provider=ProviderType.OPENAI,
        tier=ModelTier.CAPABLE,
        max_tokens=4096,
        context_window=128000,
        cost_per_1k_input=0.01,
        cost_per_1k_output=0.03,
        supports_vision=True,
        capabilities=["reasoning", "function_calling", "vision"]
    ))
    
    registry.register_model(ModelConfig(
        model_id="gpt-3.5-turbo",
        provider=ProviderType.OPENAI,
        tier=ModelTier.FAST,
        max_tokens=4096,
        context_window=16384,
        cost_per_1k_input=0.0005,
        cost_per_1k_output=0.0015,
        capabilities=["function_calling"]
    ))
    
    # Anthropic models
    registry.register_model(ModelConfig(
        model_id="claude-3-opus",
        provider=ProviderType.ANTHROPIC,
        tier=ModelTier.EXPERT,
        max_tokens=4096,
        context_window=200000,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        capabilities=["reasoning", "vision"]
    ))
    
    registry.register_model(ModelConfig(
        model_id="claude-3-sonnet",
        provider=ProviderType.ANTHROPIC,
        tier=ModelTier.BALANCED,
        max_tokens=4096,
        context_window=200000,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        capabilities=["vision"]
    ))
    
    registry.register_model(ModelConfig(
        model_id="claude-3-haiku",
        provider=ProviderType.ANTHROPIC,
        tier=ModelTier.FAST,
        max_tokens=4096,
        context_window=200000,
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        capabilities=[]
    ))
    
    return registry
