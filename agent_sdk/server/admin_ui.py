"""Compatibility shim for the platform-owned admin UI."""

from agent_sdk._deprecation import warn_platform_ownership

warn_platform_ownership("agent_sdk.server.admin_ui.ADMIN_HTML", "agent_platform.admin_ui.ADMIN_HTML")

from agent_platform.admin_ui import ADMIN_HTML  # noqa: E402
