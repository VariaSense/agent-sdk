import os

from agent_sdk.config.loader import load_config
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.observability.otel import ObservabilityManager


def main() -> None:
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(
                """
models:
  mock:
    name: mock
    provider: mock
    model_id: mock
agents:
  planner:
    model: mock
  executor:
    model: mock
rate_limits: []
"""
            )
    planner, executor = load_config(config_path, MockLLMClient())
    obs = ObservabilityManager(service_name="agent-sdk-demo")
    planner.context.config["observability"] = obs
    executor.context.config["observability"] = obs
    runtime = PlannerExecutorRuntime(planner, executor)
    runtime.run("hello tracing demo")
    print("Spans:")
    for span in obs.tracer.spans.values():
        print(f"- {span.name} ({span.status})")


if __name__ == "__main__":
    main()
