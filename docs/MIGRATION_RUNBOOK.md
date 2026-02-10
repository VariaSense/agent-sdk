# Migration Runbook

This runbook covers schema initialization and upgrades for storage backends.

## Prerequisites
- Ensure the target database is reachable.
- Backup existing data before running migrations.

## Schema Initialization
Use the migration helper to initialize schemas:

```bash
AGENT_SDK_STORAGE_BACKEND=sqlite AGENT_SDK_DB_PATH=agent_sdk.db python scripts/migrate_storage.py
```

For Postgres:

```bash
AGENT_SDK_STORAGE_BACKEND=postgres AGENT_SDK_POSTGRES_DSN=postgresql://... python scripts/migrate_storage.py
```

### Control Plane (Optional)
To initialize the control plane storage:

```bash
AGENT_SDK_CONTROL_PLANE_BACKEND=sqlite AGENT_SDK_CONTROL_PLANE_DB_PATH=control_plane.db python scripts/migrate_storage.py
```

For Postgres:

```bash
AGENT_SDK_CONTROL_PLANE_BACKEND=postgres AGENT_SDK_CONTROL_PLANE_DSN=postgresql://... python scripts/migrate_storage.py
```

## Alembic Migrations
Use Alembic for versioned upgrades and schema compatibility checks.

```bash
AGENT_SDK_ALEMBIC_DSN=postgresql://... python scripts/migrate_alembic.py
```

For SQLite:

```bash
AGENT_SDK_ALEMBIC_DSN=sqlite:///agent_sdk.db python scripts/migrate_alembic.py
```

## Upgrade Workflow
1. Stop the API server.
2. Backup database.
3. Run migration helper to ensure new columns exist.
4. Restart API server and monitor logs.
