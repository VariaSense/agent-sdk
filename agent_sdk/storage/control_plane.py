"""Compatibility shim for the platform-owned control plane backends."""

from agent_sdk._deprecation import warn_platform_ownership
from agent_platform.control_plane import (  # noqa: E402
    ControlPlaneBackend as _PlatformControlPlaneBackend,
    PostgresControlPlane as _PlatformPostgresControlPlane,
    SQLiteControlPlane as _PlatformSQLiteControlPlane,
)

warn_platform_ownership("agent_sdk.storage.control_plane", "agent_platform.control_plane")


class ControlPlaneBackend(_PlatformControlPlaneBackend):
    pass


class SQLiteControlPlane(_PlatformSQLiteControlPlane):
    def __init__(self, *args, **kwargs):
        warn_platform_ownership("agent_sdk.storage.control_plane.SQLiteControlPlane", "agent_platform.control_plane.SQLiteControlPlane")
        super().__init__(*args, **kwargs)


class PostgresControlPlane(_PlatformPostgresControlPlane):
    def __init__(self, *args, **kwargs):
        warn_platform_ownership("agent_sdk.storage.control_plane.PostgresControlPlane", "agent_platform.control_plane.PostgresControlPlane")
        super().__init__(*args, **kwargs)

__all__ = [
    "ControlPlaneBackend",
    "PostgresControlPlane",
    "SQLiteControlPlane",
]
