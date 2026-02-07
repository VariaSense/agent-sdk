# Phase 3 Deployment Blueprint

## Overview
This blueprint describes a minimal production-ish setup for Gateway mode with Postgres and the admin UI enabled. It is intended for local or single-node deployments.

## Services
- `agent-sdk`: FastAPI server with SSE, Gateway WebSocket, admin UI.
- `postgres`: storage backend for runs/sessions/events and tenant metadata.

## Environment Variables
- `API_KEY`: bootstrap API key (required).
- `AGENT_SDK_STORAGE_BACKEND=postgres`.
- `AGENT_SDK_POSTGRES_DSN=postgresql://agentuser:changeme@postgres:5432/agent_sdk`.
- `AGENT_SDK_GATEWAY_QUEUE=100` (optional).

## Docker Compose Example
```yaml
version: '3.8'

services:
  agent-sdk:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "9000:9000"
    environment:
      API_KEY: dev-key
      AGENT_SDK_STORAGE_BACKEND: postgres
      AGENT_SDK_POSTGRES_DSN: postgresql://agentuser:changeme@postgres:5432/agent_sdk
      CONFIG_PATH: /app/config.yaml
    volumes:
      - ./config.yaml:/app/config.yaml
    depends_on:
      - postgres
    networks:
      - agent-network

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: agent_sdk
      POSTGRES_USER: agentuser
      POSTGRES_PASSWORD: changeme
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - agent-network

networks:
  agent-network:
    driver: bridge

volumes:
  postgres_data:
```

## Operational Notes
- The admin UI is available at `/admin`.
- WebSocket Gateway is available at `/ws`.
- Validate readiness at `/ready`.
- Consider a reverse proxy with TLS for production.
