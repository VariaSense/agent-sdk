#!/bin/bash

# Create root folder
mkdir -p agent_sdk

# Core modules
mkdir -p agent_sdk/core
touch agent_sdk/core/__init__.py
touch agent_sdk/core/messages.py
touch agent_sdk/core/tools.py
touch agent_sdk/core/agent.py
touch agent_sdk/core/context.py
touch agent_sdk/core/runtime.py

# Config
mkdir -p agent_sdk/config
touch agent_sdk/config/__init__.py
touch agent_sdk/config/model_config.py
touch agent_sdk/config/rate_limit.py
touch agent_sdk/config/loader.py

# LLM providers
mkdir -p agent_sdk/llm
touch agent_sdk/llm/__init__.py
touch agent_sdk/llm/base.py
touch agent_sdk/llm/mock.py

# Planning
mkdir -p agent_sdk/planning
touch agent_sdk/planning/__init__.py
touch agent_sdk/planning/plan_schema.py
touch agent_sdk/planning/planner.py

# Execution
mkdir -p agent_sdk/execution
touch agent_sdk/execution/__init__.py
touch agent_sdk/execution/step_result.py
touch agent_sdk/execution/executor.py

# Observability
mkdir -p agent_sdk/observability
touch agent_sdk/observability/__init__.py
touch agent_sdk/observability/events.py
touch agent_sdk/observability/sinks.py
touch agent_sdk/observability/bus.py

# Plugins
mkdir -p agent_sdk/plugins
touch agent_sdk/plugins/__init__.py
touch agent_sdk/plugins/loader.py

# CLI
mkdir -p agent_sdk/cli
touch agent_sdk/cli/__init__.py
touch agent_sdk/cli/main.py
touch agent_sdk/cli/commands.py

# Server
mkdir -p agent_sdk/server
touch agent_sdk/server/__init__.py
touch agent_sdk/server/app.py

# Dashboard backend
mkdir -p agent_sdk/dashboard
touch agent_sdk/dashboard/__init__.py
touch agent_sdk/dashboard/server.py

# Root package init
touch agent_sdk/__init__.py

# Create pyproject.toml
cat << 'EOF' > pyproject.toml
[project]
name = "agent-sdk"
version = "0.1.0"
description = "A modular agent framework with planning, execution, tools, rate limiting, observability, plugins, and dashboard."
authors = [{ name="Hongwei" }]
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
    "pyyaml>=6.0",
    "typer>=0.12.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
]

[project.scripts]
agent-sdk = "agent_sdk.cli.main:main"

[project.entry-points."agent_sdk.tools"]
# plugin_name = "module:function"

[project.entry-points."agent_sdk.agents"]
# plugin_name = "module:AgentClass"

[project.entry-points."agent_sdk.llm"]
# plugin_name = "module:LLMClientClass"
EOF

# Create README
cat << 'EOF' > README.md
# Agent SDK

A modular, extensible agent framework featuring:

- Planner + Executor architecture
- Tooling system with decorators
- LLM abstraction layer
- Rate limiting
- Observability (events, sinks, dashboard)
- Plugin system (tools, agents, LLM providers)
- CLI (`agent-sdk`)
- Async support
- Local agent server
- Dashboard (FastAPI + SSE)

EOF

echo "agent-sdk directory tree created successfully."
