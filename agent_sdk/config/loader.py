import yaml
from agent_sdk import (
    ModelConfig, RateLimitRule, RateLimiter,
    PlannerAgent, ExecutorAgent,
    AgentContext, GLOBAL_TOOL_REGISTRY,
)
from agent_sdk.llm.base import LLMClient

def load_config(path: str, llm_client: LLMClient):
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)

    models = {
        name: ModelConfig(**m)
        for name, m in cfg.get("models", {}).items()
    }

    rules = [RateLimitRule(**r) for r in cfg.get("rate_limits", [])]
    rate_limiter = RateLimiter(rules)

    tools = GLOBAL_TOOL_REGISTRY.tools

    planner_cfg = cfg["agents"]["planner"]
    executor_cfg = cfg["agents"]["executor"]

    planner_context = AgentContext(
        tools=tools,
        model_config=models[planner_cfg["model"]],
        events=None,
        rate_limiter=rate_limiter,
    )

    executor_context = AgentContext(
        tools=tools,
        model_config=models[executor_cfg["model"]],
        events=None,
        rate_limiter=rate_limiter,
    )

    planner = PlannerAgent("planner", planner_context, llm_client)
    executor = ExecutorAgent("executor", executor_context, llm_client)

    return planner, executor
