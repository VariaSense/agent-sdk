"""Simple migration helper to initialize storage schemas."""

import os

from agent_sdk.storage import SQLiteStorage, PostgresStorage
from agent_sdk.storage.control_plane import SQLiteControlPlane, PostgresControlPlane


def main() -> None:
    backend = os.getenv("AGENT_SDK_STORAGE_BACKEND", "sqlite").lower()
    if backend == "postgres":
        dsn = os.getenv("AGENT_SDK_POSTGRES_DSN")
        if not dsn:
            raise SystemExit("AGENT_SDK_POSTGRES_DSN is required for postgres migrations")
        if PostgresStorage is None:
            raise SystemExit("psycopg is required for postgres migrations")
        PostgresStorage(dsn, initialize_schema=True)
        print("Postgres schema initialized")
    else:
        db_path = os.getenv("AGENT_SDK_DB_PATH", "agent_sdk.db")
        SQLiteStorage(db_path)
        print(f"SQLite schema initialized at {db_path}")

    control_plane_backend = os.getenv("AGENT_SDK_CONTROL_PLANE_BACKEND", "memory").lower()
    if control_plane_backend == "postgres":
        cp_dsn = os.getenv("AGENT_SDK_CONTROL_PLANE_DSN") or os.getenv("AGENT_SDK_POSTGRES_DSN")
        if not cp_dsn:
            raise SystemExit("AGENT_SDK_CONTROL_PLANE_DSN is required for postgres control plane")
        PostgresControlPlane(cp_dsn, initialize_schema=True)
        print("Postgres control plane initialized")
    elif control_plane_backend == "sqlite":
        cp_path = os.getenv("AGENT_SDK_CONTROL_PLANE_DB_PATH", "control_plane.db")
        SQLiteControlPlane(cp_path)
        print(f"SQLite control plane initialized at {cp_path}")


if __name__ == "__main__":
    main()
