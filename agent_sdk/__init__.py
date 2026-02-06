from .core.agent import Agent
from .core.context import AgentContext
from .core.tools import Tool, ToolRegistry, tool, GLOBAL_TOOL_REGISTRY
from .core.runtime import PlannerExecutorRuntime

from .planning.planner import PlannerAgent
from .planning.plan_schema import Plan, PlanStep

from .execution.executor import ExecutorAgent

from .llm.base import LLMClient, LLMResponse
from .llm.mock import MockLLMClient

from .config.model_config import ModelConfig
from .config.rate_limit import RateLimitRule, RateLimiter

from .observability.bus import EventBus
from .observability.sinks import ConsoleSink, JSONLSink
from .observability.events import ObsEvent
from .storage import StorageBackend, SQLiteStorage
from .presets import PresetDefinition, list_presets, get_preset, get_preset_config
from .tool_packs import TOOL_PACKS, GLOBAL_TOOL_METADATA, load_builtin_tool_packs

from .plugins.loader import PluginLoader
# Documentation access
from . import docs

__version__ = "0.1.0"
__all__ = [
    "Agent",
    "AgentContext",
    "Tool",
    "ToolRegistry",
    "tool",
    "GLOBAL_TOOL_REGISTRY",
    "PlannerExecutorRuntime",
    "PlannerAgent",
    "Plan",
    "PlanStep",
    "ExecutorAgent",
    "LLMClient",
    "LLMResponse",
    "MockLLMClient",
    "ModelConfig",
    "RateLimitRule",
    "RateLimiter",
    "EventBus",
    "ConsoleSink",
    "JSONLSink",
    "ObsEvent",
    "StorageBackend",
    "SQLiteStorage",
    "PresetDefinition",
    "list_presets",
    "get_preset",
    "get_preset_config",
    "TOOL_PACKS",
    "GLOBAL_TOOL_METADATA",
    "load_builtin_tool_packs",
    "PluginLoader",
    "docs",
]

# Auto-load built-in tools/metadata on import.
load_builtin_tool_packs()
