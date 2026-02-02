# Agent SDK

A modular, extensible agent framework featuring:

- Planner + Executor architecture
- Tooling system with decorators and registry
- LLM abstraction layer
- Rate limiting (per model/agent, tokens + calls)
- Observability (events, sinks, dashboard backend)
- Plugin system (tools, agents, LLM providers via entry points)
- Async support (LLM, tools, runtime)
- CLI (`agent-sdk`)
- Local agent server (FastAPI)
- Dashboard (FastAPI + SSE)

## Quickstart

```bash
pip install -e .
agent-sdk init project my-app
cd my-app
python -c "from tools import echo; print('ok')"

