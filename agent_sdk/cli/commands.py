import asyncio
import os
import typer
import yaml
import shutil
import json
import subprocess
import csv
import io
from datetime import datetime, timezone
import secrets
import zipfile

from agent_sdk.config.loader import load_config
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.core.tools import GLOBAL_TOOL_REGISTRY
from agent_sdk.plugins.loader import PluginLoader
from agent_sdk.presets.runtime import build_runtime_from_preset
from agent_sdk.storage.control_plane import SQLiteControlPlane, PostgresControlPlane
from agent_sdk.server.multi_tenant import BackupRecord
from agent_sdk.registry.local import LocalRegistry
from agent_sdk.tool_packs.manifest import ToolManifest, sign_manifest, default_manifest_secret
from agent_sdk.storage import SQLiteStorage, PostgresStorage
from agent_sdk.billing import generate_chargeback_report

run_cmd = typer.Typer(help="Run tasks using the agent runtime")
tools_cmd = typer.Typer(help="Inspect tools")
agents_cmd = typer.Typer(help="Inspect agents")
init_cmd = typer.Typer(help="Project scaffolding")
serve_cmd = typer.Typer(help="Serve agents over HTTP")
doctor_cmd = typer.Typer(help="Diagnostics and health checks")
backup_cmd = typer.Typer(help="Backup and restore storage/control plane data")
registry_cmd = typer.Typer(help="Tool pack registry operations")
compliance_cmd = typer.Typer(help="Compliance reporting")
compat_cmd = typer.Typer(help="Versioning and compatibility")
billing_cmd = typer.Typer(help="Billing and chargeback reporting")


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


def _load_control_plane_backend():
    backend = os.getenv("AGENT_SDK_CONTROL_PLANE_BACKEND", "sqlite").lower()
    if backend == "postgres":
        dsn = os.getenv("AGENT_SDK_CONTROL_PLANE_DSN") or os.getenv("AGENT_SDK_POSTGRES_DSN")
        if not dsn:
            raise typer.BadParameter("AGENT_SDK_CONTROL_PLANE_DSN is required for postgres control plane")
        return PostgresControlPlane(dsn)
    if backend == "sqlite":
        path = os.getenv("AGENT_SDK_CONTROL_PLANE_DB_PATH", "control_plane.db")
        return SQLiteControlPlane(path)
    raise typer.BadParameter(f"Unsupported control plane backend: {backend}")


def _load_storage_backend():
    backend = os.getenv("AGENT_SDK_STORAGE_BACKEND", "sqlite").lower()
    if backend == "postgres":
        dsn = os.getenv("AGENT_SDK_POSTGRES_DSN")
        if not dsn:
            raise typer.BadParameter("AGENT_SDK_POSTGRES_DSN is required for postgres storage")
        if PostgresStorage is None:
            raise typer.BadParameter("psycopg is required for postgres storage")
        return PostgresStorage(dsn)
    if backend == "sqlite":
        path = os.getenv("AGENT_SDK_DB_PATH", "agent_sdk.db")
        return SQLiteStorage(path)
    raise typer.BadParameter(f"Unsupported storage backend: {backend}")


def _require_pg_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise typer.BadParameter(f"{name} is required on PATH for Postgres backups")
    return path


@doctor_cmd.command("env-parity")
def env_parity(env_dir: str = "deploy/env") -> None:
    """Check parity of environment example files."""
    from agent_sdk.config.parity import check_env_parity

    missing = check_env_parity(env_dir)
    if not missing:
        typer.echo("env parity: ok")
        return
    typer.echo("env parity: mismatched keys detected")
    for name, keys in missing.items():
        typer.echo(f"{name}: missing {', '.join(keys)}")
    raise typer.Exit(code=1)


@compat_cmd.command("upgrade-check")
def upgrade_check(
    target: str = typer.Argument(..., help="Target SDK version to compare against"),
    current: str = typer.Option(None, "--current", help="Current SDK version (defaults to installed)"),
):
    """Check compatibility between current and target SDK versions."""
    from agent_sdk.versioning import check_compatibility
    from agent_sdk import __version__

    current_version = current or __version__
    result = check_compatibility(current_version, target)
    status = "compatible" if result.compatible else "incompatible"
    typer.echo(
        f"{status}: {result.reason} (current={result.current}, target={result.target})"
    )

@backup_cmd.command("list")
def list_backups():
    """List backup records from the control plane."""
    backend = _load_control_plane_backend()
    records = backend.list_backup_records()
    for record in records:
        typer.echo(f"{record.backup_id}\t{record.created_at}\t{record.label or ''}")


@backup_cmd.command("create")
def create_backup(
    output_dir: str = "backups",
    label: str = "",
    dry_run: bool = False,
):
    """Create a backup for storage and control plane data."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_id = f"backup_{secrets.token_hex(4)}"

    storage_backend = os.getenv("AGENT_SDK_STORAGE_BACKEND", "sqlite").lower()
    storage_path = os.getenv("AGENT_SDK_DB_PATH", "agent_sdk.db")
    control_plane_backend = os.getenv("AGENT_SDK_CONTROL_PLANE_BACKEND", "sqlite").lower()
    control_plane_path = os.getenv("AGENT_SDK_CONTROL_PLANE_DB_PATH", "control_plane.db")

    metadata = {"timestamp": timestamp}
    storage_backup_path = None
    control_plane_backup_path = None

    if storage_backend == "sqlite":
        storage_backup_path = os.path.join(output_dir, f"{backup_id}_storage.sqlite")
        if not dry_run:
            shutil.copy2(storage_path, storage_backup_path)
    elif storage_backend == "postgres":
        pg_dump = _require_pg_command("pg_dump")
        storage_backup_path = os.path.join(output_dir, f"{backup_id}_storage.sql")
        dsn = os.getenv("AGENT_SDK_POSTGRES_DSN")
        if not dsn:
            raise typer.BadParameter("AGENT_SDK_POSTGRES_DSN is required for postgres storage")
        if not dry_run:
            subprocess.run([pg_dump, "--dbname", dsn, "--file", storage_backup_path], check=True)
    else:
        raise typer.BadParameter(f"Unsupported storage backend: {storage_backend}")

    if control_plane_backend == "sqlite":
        control_plane_backup_path = os.path.join(output_dir, f"{backup_id}_control_plane.sqlite")
        if not dry_run:
            shutil.copy2(control_plane_path, control_plane_backup_path)
    elif control_plane_backend == "postgres":
        pg_dump = _require_pg_command("pg_dump")
        control_plane_backup_path = os.path.join(output_dir, f"{backup_id}_control_plane.sql")
        dsn = os.getenv("AGENT_SDK_CONTROL_PLANE_DSN") or os.getenv("AGENT_SDK_POSTGRES_DSN")
        if not dsn:
            raise typer.BadParameter("AGENT_SDK_CONTROL_PLANE_DSN is required for postgres control plane")
        if not dry_run:
            subprocess.run([pg_dump, "--dbname", dsn, "--file", control_plane_backup_path], check=True)
    else:
        raise typer.BadParameter(f"Unsupported control plane backend: {control_plane_backend}")

    record = BackupRecord(
        backup_id=backup_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        label=label or None,
        storage_backend=storage_backend,
        storage_path=storage_backup_path,
        control_plane_backend=control_plane_backend,
        control_plane_path=control_plane_backup_path,
        metadata=metadata,
    )
    backend = _load_control_plane_backend()
    if not dry_run:
        backend.create_backup_record(record)
    typer.echo(json.dumps(record.__dict__, default=str))


@backup_cmd.command("restore")
def restore_backup(
    backup_id: str,
    dry_run: bool = False,
):
    """Restore from a backup record."""
    backend = _load_control_plane_backend()
    record = backend.get_backup_record(backup_id)
    if not record:
        raise typer.BadParameter(f"Backup {backup_id} not found")

    storage_backend = os.getenv("AGENT_SDK_STORAGE_BACKEND", "sqlite").lower()
    control_plane_backend = os.getenv("AGENT_SDK_CONTROL_PLANE_BACKEND", "sqlite").lower()
    storage_path = os.getenv("AGENT_SDK_DB_PATH", "agent_sdk.db")
    control_plane_path = os.getenv("AGENT_SDK_CONTROL_PLANE_DB_PATH", "control_plane.db")

    if record.storage_backend != storage_backend:
        raise typer.BadParameter("Storage backend mismatch for restore")
    if record.control_plane_backend != control_plane_backend:
        raise typer.BadParameter("Control plane backend mismatch for restore")

    if storage_backend == "sqlite":
        if not record.storage_path:
            raise typer.BadParameter("No storage backup path recorded")
        if not dry_run:
            shutil.copy2(record.storage_path, storage_path)
    elif storage_backend == "postgres":
        psql = _require_pg_command("psql")
        dsn = os.getenv("AGENT_SDK_POSTGRES_DSN")
        if not dsn:
            raise typer.BadParameter("AGENT_SDK_POSTGRES_DSN is required for postgres restore")
        if not record.storage_path:
            raise typer.BadParameter("No storage backup path recorded")
        if not dry_run:
            subprocess.run(
                [psql, "--set", "ON_ERROR_STOP=on", "--dbname", dsn, "--file", record.storage_path],
                check=True,
            )

    if control_plane_backend == "sqlite":
        if not record.control_plane_path:
            raise typer.BadParameter("No control plane backup path recorded")
        if not dry_run:
            shutil.copy2(record.control_plane_path, control_plane_path)
    elif control_plane_backend == "postgres":
        psql = _require_pg_command("psql")
        dsn = os.getenv("AGENT_SDK_CONTROL_PLANE_DSN") or os.getenv("AGENT_SDK_POSTGRES_DSN")
        if not dsn:
            raise typer.BadParameter("AGENT_SDK_CONTROL_PLANE_DSN is required for postgres restore")
        if not record.control_plane_path:
            raise typer.BadParameter("No control plane backup path recorded")
        if not dry_run:
            subprocess.run(
                [psql, "--set", "ON_ERROR_STOP=on", "--dbname", dsn, "--file", record.control_plane_path],
                check=True,
            )

    typer.echo(f"Restore {'validated' if dry_run else 'completed'} for {backup_id}")

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


@registry_cmd.command("list")
def registry_list(name: str = "", root: str = "tool_registry"):
    registry = LocalRegistry(root=root)
    manifests = registry.list_manifests(name or None)
    for manifest in manifests:
        typer.echo(f"{manifest.name}@{manifest.version}")


@registry_cmd.command("publish")
def registry_publish(
    name: str,
    version: str,
    tools: str,
    root: str = "tool_registry",
    metadata: str = "{}",
):
    registry = LocalRegistry(root=root)
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("metadata must be valid JSON") from exc
    manifest = ToolManifest(
        name=name,
        version=version,
        tools=[t.strip() for t in tools.split(",") if t.strip()],
        metadata=meta,
    )
    secret = default_manifest_secret()
    if secret:
        manifest = sign_manifest(manifest, secret)
    registry.publish(manifest)
    typer.echo(json.dumps(manifest.to_dict(), indent=2))


@registry_cmd.command("pull")
def registry_pull(name: str, version: str = "", root: str = "tool_registry"):
    registry = LocalRegistry(root=root)
    manifest = registry.pull(name, version or None)
    typer.echo(json.dumps(manifest.to_dict(), indent=2))


@compliance_cmd.command("report")
def compliance_report(output: str = "compliance_report.zip"):
    """Generate a compliance evidence bundle."""
    backend = _load_control_plane_backend()
    bundles = backend.list_policy_bundles()
    retention = []
    try:
        retention = backend.list_orgs()
    except Exception:
        retention = []
    evidence = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_bundles": [bundle.__dict__ for bundle in bundles],
        "orgs": [org.__dict__ for org in retention],
        "env": {
            "AGENT_SDK_AUDIT_HASH_CHAIN": os.getenv("AGENT_SDK_AUDIT_HASH_CHAIN"),
            "AGENT_SDK_RETENTION_DEFAULT": os.getenv("AGENT_SDK_EVENT_RETENTION_MAX_EVENTS"),
        },
    }
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("compliance.json", json.dumps(evidence, indent=2))
    typer.echo(f"Wrote {output}")


@billing_cmd.command("export")
def billing_export(
    format: str = typer.Option("json", "--format", help="Output format: json or csv"),
    org_id: str = typer.Option(None, "--org-id", help="Filter by org id"),
    group_by: str = typer.Option("org_id,project", "--group-by", help="Comma-separated group fields"),
    limit: int = typer.Option(1000, "--limit", help="Max runs to include"),
    output: str = typer.Option(None, "--output", help="Write output to file"),
):
    """Generate a chargeback report from stored runs."""
    storage = _load_storage_backend()
    runs = storage.list_runs(org_id=org_id, limit=limit)
    report = generate_chargeback_report(runs, group_by=group_by)
    fmt = format.lower()
    if fmt == "csv":
        group_fields = [field.strip() for field in group_by.split(",") if field.strip()]
        if not group_fields:
            group_fields = ["org_id"]
        output_buffer = io.StringIO()
        writer = csv.writer(output_buffer)
        header = group_fields + ["run_count", "session_count", "token_count", "cost_usd"]
        writer.writerow(header)
        for row in report:
            writer.writerow([row.get(col) for col in header])
        payload = output_buffer.getvalue()
    elif fmt == "json":
        payload = json.dumps({"results": report, "count": len(report)}, indent=2)
    else:
        raise typer.BadParameter("format must be json or csv")

    if output:
        with open(output, "w", encoding="utf-8") as handle:
            handle.write(payload)
        typer.echo(f"Wrote {output}")
    else:
        typer.echo(payload)
