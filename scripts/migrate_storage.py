"""Simple migration helper to initialize storage schemas."""

import os

from agent_sdk.storage import SQLiteStorage, PostgresStorage


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
        return
    db_path = os.getenv("AGENT_SDK_DB_PATH", "agent_sdk.db")
    SQLiteStorage(db_path)
    print(f"SQLite schema initialized at {db_path}")


if __name__ == "__main__":
    main()
