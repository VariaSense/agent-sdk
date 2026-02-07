"""In-memory multi-tenant data model for orgs, users, and API keys."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import secrets


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Organization:
    org_id: str
    name: str
    created_at: str = field(default_factory=_now_iso)
    quotas: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class User:
    user_id: str
    org_id: str
    name: str
    created_at: str = field(default_factory=_now_iso)


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


@dataclass
class UsageSummary:
    org_id: str
    run_count: int = 0
    session_count: int = 0
    last_run_at: Optional[str] = None
    last_session_at: Optional[str] = None


class MultiTenantStore:
    """Simple in-memory registry for multi-tenant admin surfaces."""

    def __init__(self):
        self._orgs: Dict[str, Organization] = {}
        self._users: Dict[str, User] = {}
        self._keys: Dict[str, APIKeyRecord] = {}
        self._usage: Dict[str, UsageSummary] = {}
        self.ensure_org("default", "Default Org")

    def ensure_org(self, org_id: str, name: Optional[str] = None) -> Organization:
        if org_id in self._orgs:
            return self._orgs[org_id]
        org = Organization(org_id=org_id, name=name or org_id)
        self._orgs[org_id] = org
        self._usage.setdefault(org_id, UsageSummary(org_id=org_id))
        return org

    def list_orgs(self) -> List[Organization]:
        return list(self._orgs.values())

    def create_user(self, org_id: str, name: str) -> User:
        self.ensure_org(org_id)
        user_id = f"user_{secrets.token_hex(8)}"
        user = User(user_id=user_id, org_id=org_id, name=name)
        self._users[user_id] = user
        return user

    def list_users(self, org_id: Optional[str] = None) -> List[User]:
        if org_id is None:
            return list(self._users.values())
        return [user for user in self._users.values() if user.org_id == org_id]

    def create_api_key(self, org_id: str, label: str, role: str = "developer", scopes: Optional[List[str]] = None) -> APIKeyRecord:
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
        )
        self._keys[key_id] = record
        return record

    def register_api_key(self, org_id: str, key: str, label: str, role: str = "developer", scopes: Optional[List[str]] = None) -> APIKeyRecord:
        self.ensure_org(org_id)
        key_id = f"key_{secrets.token_hex(6)}"
        record = APIKeyRecord(
            key_id=key_id,
            org_id=org_id,
            key=key,
            label=label,
            role=role,
            scopes=scopes or [],
        )
        self._keys[key_id] = record
        return record

    def list_api_keys(self, org_id: Optional[str] = None) -> List[APIKeyRecord]:
        if org_id is None:
            return list(self._keys.values())
        return [record for record in self._keys.values() if record.org_id == org_id]

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

    def usage_summary(self, org_id: Optional[str] = None) -> List[UsageSummary]:
        if org_id is None:
            return list(self._usage.values())
        summary = self._usage.get(org_id)
        return [summary] if summary else []
