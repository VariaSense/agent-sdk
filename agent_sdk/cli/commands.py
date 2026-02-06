import asyncio
import typer
import yaml

from agent_sdk.config.loader import load_config
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.core.tools import GLOBAL_TOOL_REGISTRY
from agent_sdk.plugins.loader import PluginLoader
from agent_sdk.presets.runtime import build_runtime_from_preset

run_cmd = typer.Typer(help="Run tasks using the agent runtime")
tools_cmd = typer.Typer(help="Inspect tools")
agents_cmd = typer.Typer(help="Inspect agents")
init_cmd = typer.Typer(help="Project scaffolding")
serve_cmd = typer.Typer(help="Serve agents over HTTP")

@run_cmd.command("task")
def run_task(task: str, config: str = "config.yaml", preset: str = ""):
    loader = PluginLoader()
    loader.load()
    if preset:
        runtime = build_runtime_from_preset(preset, MockLLMClient())
    else:
        planner, executor = load_config(config, MockLLMClient())
        runtime = PlannerExecutorRuntime(planner, executor)
    msgs = asyncio.run(runtime.run_async(task))
    for m in msgs:
        typer.echo(f"{m.role.upper()}: {m.content}")

@run_cmd.command("file")
def run_file(file: str, config: str = "config.yaml", preset: str = ""):
    with open(file, "r") as f:
        data = yaml.safe_load(f)
    task = data["task"]
    loader = PluginLoader()
    loader.load()
    if preset:
        runtime = build_runtime_from_preset(preset, MockLLMClient())
    else:
        planner, executor = load_config(config, MockLLMClient())
        runtime = PlannerExecutorRuntime(planner, executor)
    msgs = asyncio.run(runtime.run_async(task))
    for m in msgs:
        typer.echo(f"{m.role.upper()}: {m.content}")

@tools_cmd.command("list")
def list_tools():
    for name, tool in GLOBAL_TOOL_REGISTRY.tools.items():
        typer.echo(f"- {name}: {tool.description}")

@agents_cmd.command("list")
def list_agents(config: str = "config.yaml"):
    with open(config, "r") as f:
        cfg = yaml.safe_load(f)
    for name in cfg.get("agents", {}).keys():
        typer.echo(f"- {name}")

@init_cmd.command("project")
def init_project(name: str = "agent-app"):
    import os, textwrap
    os.makedirs(name, exist_ok=True)
    with open(os.path.join(name, "config.yaml"), "w") as f:
        f.write(textwrap.dedent("""
        models:
          planner:
            name: planner-gpt4
            provider: openai
            model_id: gpt-4o
            temperature: 0.1
            max_tokens: 2048

          executor:
            name: executor-mini
            provider: openai
            model_id: gpt-4o-mini
            temperature: 0.3
            max_tokens: 1024

        rate_limits: []
        agents:
          planner:
            model: planner
          executor:
            model: executor
        """).strip() + "\n")

    with open(os.path.join(name, "tools.py"), "w") as f:
        f.write(textwrap.dedent("""
        from agent_sdk import tool

        @tool("echo", "Echo back input")
        def echo(args):
            return args["text"]
        """).strip() + "\n")

    typer.echo(f"Initialized agent project in ./{name}")

@serve_cmd.command("http")
def serve_http(config: str = "config.yaml", host: str = "0.0.0.0", port: int = 9000):
    import uvicorn
    from agent_sdk.server.app import create_app
    loader = PluginLoader()
    loader.load()
    app = create_app(config)
    uvicorn.run(app, host=host, port=port)
