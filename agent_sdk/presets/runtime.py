"""
Runtime helpers for presets.
"""

from __future__ import annotations

from typing import Dict

from agent_sdk.core.context import AgentContext
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.core.tools import GLOBAL_TOOL_REGISTRY
from agent_sdk.execution.executor import ExecutorAgent
from agent_sdk.llm.base import LLMClient
from agent_sdk.planning.planner import PlannerAgent
from agent_sdk.config.model_config import ModelConfig
from agent_sdk.presets import get_preset
from agent_sdk.tool_packs import TOOL_PACKS


def _resolve_tools(tool_packs) -> Dict[str, object]:
    tool_names = []
    for pack in tool_packs:
        tool_names.extend(TOOL_PACKS.get(pack, []))
    if not tool_names:
        return GLOBAL_TOOL_REGISTRY.tools
    return {name: tool for name, tool in GLOBAL_TOOL_REGISTRY.tools.items() if name in tool_names}


def build_runtime_from_preset(preset_name: str, llm_client: LLMClient) -> PlannerExecutorRuntime:
    preset = get_preset(preset_name)
    model = ModelConfig(**preset.model)
    tools = _resolve_tools(preset.tool_packs)

    planner_context = AgentContext(
        tools=tools,
        model_config=model,
        max_short_term=int(preset.memory.get("max_short_term", 1000)),
        max_long_term=int(preset.memory.get("max_long_term", 10000)),
    )
    executor_context = AgentContext(
        tools=tools,
        model_config=model,
        max_short_term=int(preset.memory.get("max_short_term", 1000)),
        max_long_term=int(preset.memory.get("max_long_term", 10000)),
    )
    planner = PlannerAgent("planner", planner_context, llm_client)
    executor = ExecutorAgent("executor", executor_context, llm_client)
    return PlannerExecutorRuntime(planner, executor)
