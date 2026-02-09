import asyncio
import os
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
doctor_cmd = typer.Typer(help="Diagnostics and health checks")


def collect_doctor_checks(config: str) -> list[dict]:
    checks = []

    if not os.path.exists(config):
        checks.append({"name": "config.exists", "status": "fail", "detail": f"{config} not found"})
        return checks
    checks.append({"name": "config.exists", "status": "ok", "detail": config})

    try:
        with open(config, "r") as f:
            raw_cfg = yaml.safe_load(f) or {}
        load_config(config, MockLLMClient())
        checks.append({"name": "config.load", "status": "ok", "detail": "valid"})
    except Exception as exc:
        checks.append({"name": "config.load", "status": "fail", "detail": str(exc)})
        return checks

    model_providers = []
    for model in (raw_cfg.get("models") or {}).values():
        provider = (model or {}).get("provider")
        if provider:
            model_providers.append(provider)

    if "openai" in model_providers and not os.getenv("OPENAI_API_KEY"):
        checks.append({"name": "env.openai_api_key", "status": "warn", "detail": "OPENAI_API_KEY missing"})
    else:
        checks.append({"name": "env.openai_api_key", "status": "ok", "detail": "present or not required"})

    tool_count = len(GLOBAL_TOOL_REGISTRY.tools)
    if tool_count == 0:
        checks.append({"name": "tools.registered", "status": "warn", "detail": "no tools registered"})
    else:
        checks.append({"name": "tools.registered", "status": "ok", "detail": f"{tool_count} tools"})

    db_path = os.getenv("AGENT_SDK_DB_PATH", "agent_sdk.db")
    db_dir = os.path.dirname(db_path) or "."
    if os.path.isdir(db_dir) and os.access(db_dir, os.W_OK):
        checks.append({"name": "storage.db_path", "status": "ok", "detail": db_path})
    else:
        checks.append({"name": "storage.db_path", "status": "warn", "detail": f"Not writable: {db_dir}"})

    log_path = os.getenv("AGENT_SDK_RUN_LOG_PATH")
    if log_path:
        log_dir = os.path.dirname(log_path) or "."
        if os.path.isdir(log_dir) and os.access(log_dir, os.W_OK):
            checks.append({"name": "logs.run_log_path", "status": "ok", "detail": log_path})
        else:
            checks.append({"name": "logs.run_log_path", "status": "warn", "detail": f"Not writable: {log_dir}"})
    else:
        checks.append({"name": "logs.run_log_path", "status": "warn", "detail": "AGENT_SDK_RUN_LOG_PATH not set"})

    return checks

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

@init_cmd.callback(invoke_without_command=True)
def init_default(
    ctx: typer.Context,
    name: str = "agent-app",
):
    """Initialize a new agent project."""
    if ctx.invoked_subcommand is None:
        init_project(name)


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

    with open(os.path.join(name, ".env.example"), "w") as f:
        f.write("OPENAI_API_KEY=\n")

    with open(os.path.join(name, "README.md"), "w") as f:
        f.write(textwrap.dedent(f"""
        # {name}

        Example agent-sdk project scaffold.
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


@doctor_cmd.command("check")
def doctor_check(config: str = "config.yaml"):
    checks = collect_doctor_checks(config)
    for check in checks:
        status = check["status"].upper()
        typer.echo(f"[{status}] {check['name']}: {check['detail']}")
