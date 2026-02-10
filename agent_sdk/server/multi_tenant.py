"""In-memory multi-tenant data model for orgs, users, and API keys."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import secrets

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_sdk.storage.control_plane import ControlPlaneBackend


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Organization:
    org_id: str
    name: str
    created_at: str = field(default_factory=_now_iso)
    quotas: Dict[str, int] = field(default_factory=dict)
    policy_bundle_id: Optional[str] = None
    policy_bundle_version: Optional[int] = None
    policy_overrides: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class User:
    user_id: str
    org_id: str
    name: str
    created_at: str = field(default_factory=_now_iso)
    active: bool = True
    is_service_account: bool = False


@dataclass(frozen=True)
class APIKeyRecord:
    key_id: str
    org_id: str
    key: str
    label: str
    role: str = "developer"
    scopes: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    active: bool = True
    expires_at: Optional[str] = None
    rotated_at: Optional[str] = None
    rate_limit_per_minute: Optional[int] = None
    ip_allowlist: List[str] = field(default_factory=list)


@dataclass
class UsageSummary:
    org_id: str
    run_count: int = 0
    session_count: int = 0
    token_count: int = 0
    last_run_at: Optional[str] = None
    last_session_at: Optional[str] = None


@dataclass(frozen=True)
class BackupRecord:
    backup_id: str
    created_at: str
    label: Optional[str]
    storage_backend: str
    storage_path: Optional[str]
    control_plane_backend: str
    control_plane_path: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QuotaLimits:
    max_runs: Optional[int] = None
    max_sessions: Optional[int] = None
    max_tokens: Optional[int] = None


@dataclass(frozen=True)
class RetentionPolicyConfig:
    max_events: Optional[int] = None
    max_run_age_days: Optional[int] = None
    max_session_age_days: Optional[int] = None


@dataclass(frozen=True)
class ModelPolicy:
    allowed_models: List[str] = field(default_factory=list)
    fallback_models: List[str] = field(default_factory=list)


class MultiTenantStore:
    """Registry for multi-tenant admin surfaces (optionally backed by control plane storage)."""

    def __init__(self, backend: Optional["ControlPlaneBackend"] = None):
        self._backend = backend
        self._orgs: Dict[str, Organization] = {}
        self._users: Dict[str, User] = {}
        self._keys: Dict[str, APIKeyRecord] = {}
        self._usage: Dict[str, UsageSummary] = {}
        self._quotas: Dict[str, QuotaLimits] = {}
        self._retention: Dict[str, RetentionPolicyConfig] = {}
        self._residency: Dict[str, Optional[str]] = {}
        self._encryption_keys: Dict[str, Optional[str]] = {}
        self._model_policies: Dict[str, ModelPolicy] = {}
        self._policy_bundles: Dict[str, List["PolicyBundle"]] = {}
        self._policy_assignments: Dict[str, "PolicyAssignment"] = {}
        self._model_catalog: List[str] = []
        self.ensure_org("default", "Default Org")

    def ensure_org(self, org_id: str, name: Optional[str] = None) -> Organization:
        if self._backend is not None:
            return self._backend.ensure_org(org_id, name)
        if org_id in self._orgs:
            return self._orgs[org_id]
        org = Organization(org_id=org_id, name=name or org_id)
        self._orgs[org_id] = org
        self._usage.setdefault(org_id, UsageSummary(org_id=org_id))
        if org_id not in self._quotas:
            self._quotas[org_id] = QuotaLimits()
        if org_id not in self._retention:
            self._retention[org_id] = RetentionPolicyConfig()
        if org_id not in self._residency:
            self._residency[org_id] = None
        if org_id not in self._encryption_keys:
            self._encryption_keys[org_id] = None
        return org

    def list_orgs(self) -> List[Organization]:
        if self._backend is not None:
            return self._backend.list_orgs()
        return list(self._orgs.values())

    def create_user(self, org_id: str, name: str, is_service_account: bool = False) -> User:
        self.ensure_org(org_id)
        user_id = f"user_{secrets.token_hex(8)}"
        user = User(user_id=user_id, org_id=org_id, name=name, is_service_account=is_service_account)
        if self._backend is not None:
            return self._backend.create_user(org_id, user)
        self._users[user_id] = user
        return user

    def list_users(self, org_id: Optional[str] = None, active_only: bool = False) -> List[User]:
        if self._backend is not None:
            return self._backend.list_users(org_id, active_only=active_only)
        if org_id is None:
            users = list(self._users.values())
        else:
            users = [user for user in self._users.values() if user.org_id == org_id]
        if active_only:
            users = [user for user in users if user.active]
        return users

    def deactivate_user(self, user_id: str) -> bool:
        if self._backend is not None:
            return self._backend.deactivate_user(user_id)
        user = self._users.get(user_id)
        if not user:
            return False
        self._users[user_id] = User(
            user_id=user.user_id,
            org_id=user.org_id,
            name=user.name,
            created_at=user.created_at,
            active=False,
            is_service_account=user.is_service_account,
        )
        return True

    def create_api_key(
        self,
        org_id: str,
        label: str,
        role: str = "developer",
        scopes: Optional[List[str]] = None,
        expires_at: Optional[str] = None,
        rate_limit_per_minute: Optional[int] = None,
        ip_allowlist: Optional[List[str]] = None,
    ) -> APIKeyRecord:
        self.ensure_org(org_id)
        key = f"sk_{secrets.token_urlsafe(24)}"
        key_id = f"key_{secrets.token_hex(6)}"
        record = APIKeyRecord(
            key_id=key_id,
            org_id=org_id,
            key=key,
            label=label,
            role=role,
            scopes=scopes or [],
            expires_at=expires_at,
            rate_limit_per_minute=rate_limit_per_minute,
            ip_allowlist=ip_allowlist or [],
        )
        if self._backend is not None:
            return self._backend.create_api_key(record)
        self._keys[key_id] = record
        return record

    def register_api_key(
        self,
        org_id: str,
        key: str,
        label: str,
        role: str = "developer",
        scopes: Optional[List[str]] = None,
        expires_at: Optional[str] = None,
        rate_limit_per_minute: Optional[int] = None,
        ip_allowlist: Optional[List[str]] = None,
    ) -> APIKeyRecord:
        self.ensure_org(org_id)
        key_id = f"key_{secrets.token_hex(6)}"
        record = APIKeyRecord(
            key_id=key_id,
            org_id=org_id,
            key=key,
            label=label,
            role=role,
            scopes=scopes or [],
            expires_at=expires_at,
            rate_limit_per_minute=rate_limit_per_minute,
            ip_allowlist=ip_allowlist or [],
        )
        if self._backend is not None:
            return self._backend.create_api_key(record)
        self._keys[key_id] = record
        return record

    def list_api_keys(self, org_id: Optional[str] = None) -> List[APIKeyRecord]:
        if self._backend is not None:
            return self._backend.list_api_keys(org_id)
        if org_id is None:
            return list(self._keys.values())
        return [record for record in self._keys.values() if record.org_id == org_id]

    def rotate_api_key(self, key_id: str) -> Optional[Tuple[APIKeyRecord, APIKeyRecord]]:
        records = self.list_api_keys()
        current = next((r for r in records if r.key_id == key_id), None)
        if current is None:
            return None
        rotated_at = _now_iso()
        if self._backend is not None:
            self._backend.deactivate_api_key(key_id, rotated_at)
        else:
            self._keys[key_id] = APIKeyRecord(
                key_id=current.key_id,
                org_id=current.org_id,
                key=current.key,
                label=current.label,
                role=current.role,
                scopes=current.scopes,
                created_at=current.created_at,
                active=False,
                expires_at=current.expires_at,
                rotated_at=rotated_at,
            )
        new_record = self.create_api_key(
            current.org_id,
            label=current.label,
            role=current.role,
            scopes=current.scopes,
            expires_at=current.expires_at,
        )
        return new_record, current

    def record_run(self, org_id: str) -> None:
        self.ensure_org(org_id)
        summary = self._usage.setdefault(org_id, UsageSummary(org_id=org_id))
        summary.run_count += 1
        summary.last_run_at = _now_iso()

    def record_session(self, org_id: str) -> None:
        self.ensure_org(org_id)
        summary = self._usage.setdefault(org_id, UsageSummary(org_id=org_id))
        summary.session_count += 1
        summary.last_session_at = _now_iso()

    def record_tokens(self, org_id: str, tokens: int) -> None:
        if tokens <= 0:
            return
        self.ensure_org(org_id)
        summary = self._usage.setdefault(org_id, UsageSummary(org_id=org_id))
        summary.token_count += tokens

    def set_quota(self, org_id: str, limits: QuotaLimits) -> None:
        self.ensure_org(org_id)
        if self._backend is not None:
            return self._backend.set_quota(org_id, limits)
        self._quotas[org_id] = limits

    def get_quota(self, org_id: str) -> QuotaLimits:
        self.ensure_org(org_id)
        if self._backend is not None:
            return self._backend.get_quota(org_id)
        return self._quotas.get(org_id, QuotaLimits())

    def set_retention_policy(self, org_id: str, policy: RetentionPolicyConfig) -> None:
        self.ensure_org(org_id)
        if self._backend is not None:
            self._backend.set_retention_policy(org_id, policy)
            return
        self._retention[org_id] = policy

    def get_retention_policy(self, org_id: str) -> RetentionPolicyConfig:
        self.ensure_org(org_id)
        if self._backend is not None:
            policy = self._backend.get_retention_policy(org_id)
            if policy is not None:
                return policy
        return self._retention.get(org_id, RetentionPolicyConfig())

    def set_residency(self, org_id: str, region: Optional[str]) -> None:
        self.ensure_org(org_id)
        if self._backend is not None:
            self._backend.set_residency(org_id, region)
            return
        self._residency[org_id] = region

    def get_residency(self, org_id: str) -> Optional[str]:
        self.ensure_org(org_id)
        if self._backend is not None:
            return self._backend.get_residency(org_id)
        return self._residency.get(org_id)

    def set_encryption_key(self, org_id: str, key: Optional[str]) -> None:
        self.ensure_org(org_id)
        if self._backend is not None:
            self._backend.set_encryption_key(org_id, key)
            return
        self._encryption_keys[org_id] = key

    def get_encryption_key(self, org_id: str) -> Optional[str]:
        self.ensure_org(org_id)
        if self._backend is not None:
            return self._backend.get_encryption_key(org_id)
        return self._encryption_keys.get(org_id)

    def check_quota(self, org_id: str, new_run: bool = False, new_session: bool = False, tokens: int = 0) -> Tuple[bool, Optional[str]]:
        summary = self._usage.get(org_id, UsageSummary(org_id=org_id))
        limits = self.get_quota(org_id)
        if new_run and limits.max_runs is not None and summary.run_count >= limits.max_runs:
            return False, "run_quota_exceeded"
        if new_session and limits.max_sessions is not None and summary.session_count >= limits.max_sessions:
            return False, "session_quota_exceeded"
        if tokens > 0 and limits.max_tokens is not None and summary.token_count + tokens > limits.max_tokens:
            return False, "token_quota_exceeded"
        return True, None

    def set_model_catalog(self, models: List[str]) -> None:
        self._model_catalog = models

    def set_model_policy(self, org_id: str, allowed_models: List[str], fallback_models: Optional[List[str]] = None) -> ModelPolicy:
        self.ensure_org(org_id)
        filtered_allowed = [m for m in allowed_models if m in self._model_catalog] if self._model_catalog else allowed_models
        fallback = fallback_models or filtered_allowed
        policy = ModelPolicy(allowed_models=filtered_allowed, fallback_models=fallback)
        if self._backend is not None:
            self._backend.set_model_policy(org_id, policy)
            return policy
        self._model_policies[org_id] = policy
        return policy

    def get_model_policy(self, org_id: str) -> Optional[ModelPolicy]:
        if self._backend is not None:
            return self._backend.get_model_policy(org_id)
        return self._model_policies.get(org_id)

    def create_policy_bundle(
        self,
        bundle_id: str,
        content: Dict[str, Any],
        description: Optional[str] = None,
        version: Optional[int] = None,
    ) -> "PolicyBundle":
        from agent_sdk.policy.types import PolicyBundle

        if self._backend is not None:
            return self._backend.create_policy_bundle(
                PolicyBundle(
                    bundle_id=bundle_id,
                    version=version or 0,
                    content=content,
                    description=description,
                )
            )
        versions = self._policy_bundles.setdefault(bundle_id, [])
        next_version = version or (max((b.version for b in versions), default=0) + 1)
        bundle = PolicyBundle(
            bundle_id=bundle_id,
            version=next_version,
            content=content,
            description=description,
        )
        versions.append(bundle)
        return bundle

    def list_policy_bundles(self) -> List["PolicyBundle"]:
        from agent_sdk.policy.types import PolicyBundle

        if self._backend is not None:
            return self._backend.list_policy_bundles()
        latest: List[PolicyBundle] = []
        for versions in self._policy_bundles.values():
            if not versions:
                continue
            latest.append(max(versions, key=lambda b: b.version))
        return latest

    def list_policy_bundle_versions(self, bundle_id: str) -> List["PolicyBundle"]:
        if self._backend is not None:
            return self._backend.list_policy_bundle_versions(bundle_id)
        return sorted(self._policy_bundles.get(bundle_id, []), key=lambda b: b.version)

    def get_policy_bundle(self, bundle_id: str, version: Optional[int] = None) -> Optional["PolicyBundle"]:
        if self._backend is not None:
            return self._backend.get_policy_bundle(bundle_id, version=version)
        versions = self._policy_bundles.get(bundle_id, [])
        if not versions:
            return None
        if version is None:
            return max(versions, key=lambda b: b.version)
        for bundle in versions:
            if bundle.version == version:
                return bundle
        return None

    def assign_policy_bundle(
        self,
        org_id: str,
        bundle_id: str,
        version: int,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> "PolicyAssignment":
        from agent_sdk.policy.types import PolicyAssignment

        self.ensure_org(org_id)
        assignment = PolicyAssignment(
            org_id=org_id,
            bundle_id=bundle_id,
            version=version,
            overrides=overrides or {},
        )
        if self._backend is not None:
            return self._backend.assign_policy_bundle(assignment)
        self._policy_assignments[org_id] = assignment
        return assignment

    def get_policy_assignment(self, org_id: str) -> Optional["PolicyAssignment"]:
        if self._backend is not None:
            return self._backend.get_policy_assignment(org_id)
        return self._policy_assignments.get(org_id)

    def resolve_model(self, org_id: str, requested: Optional[str]) -> Optional[str]:
        policy = self._model_policies.get(org_id)
        if not policy:
            return requested
        if requested and requested in policy.allowed_models:
            return requested
        if policy.fallback_models:
            return policy.fallback_models[0]
        return requested

    def usage_summary(self, org_id: Optional[str] = None) -> List[UsageSummary]:
        if org_id is None:
            return list(self._usage.values())
        summary = self._usage.get(org_id)
        return [summary] if summary else []
