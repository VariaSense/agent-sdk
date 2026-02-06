import yaml
import os
import logging
from agent_sdk import (
    ModelConfig, RateLimitRule, RateLimiter,
    PlannerAgent, ExecutorAgent,
    AgentContext, GLOBAL_TOOL_REGISTRY,
)
from agent_sdk.observability.bus import EventBus
from agent_sdk.observability.metrics_pipeline import ObsMetricsSink
from agent_sdk.llm.base import LLMClient
from agent_sdk.validators import ConfigSchema
from agent_sdk.exceptions import ConfigError

logger = logging.getLogger(__name__)


def load_config(path: str, llm_client: LLMClient):
    """Load and validate SDK configuration
    
    Args:
        path: Path to config file (YAML)
        llm_client: LLM client instance
        
    Returns:
        Tuple of (planner_agent, executor_agent)
        
    Raises:
        ConfigError: If configuration is invalid
    """
    # Expand environment variables in path
    path = os.path.expanduser(os.path.expandvars(path))
    
    try:
        with open(path, "r") as f:
            raw_cfg = yaml.safe_load(f)
            if raw_cfg is None:
                raise ConfigError("Configuration file is empty")
    except FileNotFoundError:
        raise ConfigError(f"Configuration file not found: {path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in configuration: {e}")

    # Validate configuration schema
    try:
        validated_cfg = ConfigSchema(**raw_cfg)
        logger.info(f"Configuration loaded and validated from {path}")
    except Exception as e:
        raise ConfigError(f"Configuration validation failed: {e}")

    # Build models
    models = {
        name: ModelConfig(**m.model_dump())
        for name, m in validated_cfg.models.items()
    }
    logger.debug(f"Loaded {len(models)} models: {', '.join(models.keys())}")

    # Build rate limiter
    rules = [RateLimitRule(**r) for r in validated_cfg.rate_limits]
    rate_limiter = RateLimiter(rules)
    logger.debug(f"Configured rate limiter with {len(rules)} rules")

    tools = GLOBAL_TOOL_REGISTRY.tools
    logger.debug(f"Using {len(tools)} registered tools")

    # Get agent configurations
    try:
        planner_cfg = validated_cfg.agents["planner"]
        executor_cfg = validated_cfg.agents["executor"]
    except KeyError as e:
        raise ConfigError(f"Missing required agent configuration: {e}")

    metrics_enabled = os.getenv("AGENT_SDK_METRICS_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    events = EventBus([ObsMetricsSink()]) if metrics_enabled else None

    # Create contexts
    planner_context = AgentContext(
        tools=tools,
        model_config=models[planner_cfg.model],
        events=events,
        rate_limiter=rate_limiter,
    )

    executor_context = AgentContext(
        tools=tools,
        model_config=models[executor_cfg.model],
        events=events,
        rate_limiter=rate_limiter,
    )

    # Create agents
    planner = PlannerAgent("planner", planner_context, llm_client)
    executor = ExecutorAgent("executor", executor_context, llm_client)

    logger.info("Agents initialized: planner and executor")
    return planner, executor
