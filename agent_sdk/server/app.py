"""Compatibility shim for the platform-owned hosted API app."""

from agent_sdk._deprecation import warn_platform_ownership

warn_platform_ownership("agent_sdk.server.app.create_app", "agent_platform.hosted_api.create_app")

from agent_platform.hosted_api import create_app  # noqa: E402

__all__ = ["create_app"]
