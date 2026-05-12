"""Compatibility shim for the platform-owned tenant store."""

from agent_sdk._deprecation import warn_platform_ownership
from agent_platform.tenant_store import (  # noqa: E402
    APIKeyRecord,
    BackupRecord,
    KeyUsageSummary,
    ModelPolicy,
    MultiTenantStore as _PlatformMultiTenantStore,
    Organization,
    Project,
    ProjectUsageSummary,
    QuotaLimits,
    RetentionPolicyConfig,
    SecretRotationPolicy,
    UsageSummary,
    User,
    _now_iso,
)

warn_platform_ownership("agent_sdk.server.multi_tenant", "agent_platform.tenant_store")


class MultiTenantStore(_PlatformMultiTenantStore):
    def __init__(self, *args, **kwargs):
        warn_platform_ownership("agent_sdk.server.multi_tenant.MultiTenantStore", "agent_platform.tenant_store.MultiTenantStore")
        super().__init__(*args, **kwargs)

__all__ = [
    "APIKeyRecord",
    "BackupRecord",
    "KeyUsageSummary",
    "ModelPolicy",
    "MultiTenantStore",
    "Organization",
    "Project",
    "ProjectUsageSummary",
    "QuotaLimits",
    "RetentionPolicyConfig",
    "SecretRotationPolicy",
    "UsageSummary",
    "User",
    "_now_iso",
]
