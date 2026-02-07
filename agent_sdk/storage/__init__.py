"""
Storage backends for runs, sessions, and streaming events.
"""

from agent_sdk.storage.base import StorageBackend
from agent_sdk.storage.sqlite import SQLiteStorage

try:  # optional dependency
    from agent_sdk.storage.postgres import PostgresStorage
except Exception:  # pragma: no cover - optional dependency
    PostgresStorage = None

__all__ = [
    "StorageBackend",
    "SQLiteStorage",
    "PostgresStorage",
]
