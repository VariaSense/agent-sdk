"""Compatibility shim for the platform-owned dashboard server."""

from agent_sdk._deprecation import warn_platform_ownership

warn_platform_ownership("agent_sdk.dashboard.server.DashboardServer", "agent_platform.dashboard.DashboardServer")

from agent_platform.dashboard import DashboardServer  # noqa: E402
