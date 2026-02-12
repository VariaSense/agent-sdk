"""Control plane storage for orgs, users, API keys, quotas, and model policies."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import List, Optional

from agent_sdk.server.multi_tenant import (
    Organization,
    Project,
    User,
    APIKeyRecord,
    QuotaLimits,
    RetentionPolicyConfig,
    ModelPolicy,
    BackupRecord,
    SecretRotationPolicy,
)
from agent_sdk.webhooks import WebhookSubscription
from agent_sdk.policy.types import PolicyAssignment, PolicyBundle, PolicyApproval

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None


class ControlPlaneBackend:
    def ensure_org(self, org_id: str, name: Optional[str] = None) -> Organization:
        raise NotImplementedError

    def get_org(self, org_id: str) -> Optional[Organization]:
        raise NotImplementedError

    def list_orgs(self) -> List[Organization]:
        raise NotImplementedError

    def create_project(self, project: Project) -> Project:
        raise NotImplementedError

    def list_projects(self, org_id: Optional[str] = None) -> List[Project]:
        raise NotImplementedError

    def get_project(self, project_id: str) -> Optional[Project]:
        raise NotImplementedError

    def delete_project(self, project_id: str) -> bool:
        raise NotImplementedError

    def create_user(self, org_id: str, user: User) -> User:
        raise NotImplementedError

    def list_users(self, org_id: Optional[str] = None, active_only: bool = False) -> List[User]:
        raise NotImplementedError

    def create_api_key(self, record: APIKeyRecord) -> APIKeyRecord:
        raise NotImplementedError

    def deactivate_user(self, user_id: str) -> bool:
        raise NotImplementedError

    def list_api_keys(self, org_id: Optional[str] = None) -> List[APIKeyRecord]:
        raise NotImplementedError

    def deactivate_api_key(self, key_id: str, rotated_at: str) -> None:
        raise NotImplementedError

    def delete_api_key(self, key_id: str) -> bool:
        raise NotImplementedError

    def set_quota(self, org_id: str, quota: QuotaLimits) -> None:
        raise NotImplementedError

    def get_quota(self, org_id: str) -> QuotaLimits:
        raise NotImplementedError

    def set_project_quota(self, project_id: str, quota: QuotaLimits) -> None:
        raise NotImplementedError

    def get_project_quota(self, project_id: str) -> QuotaLimits:
        raise NotImplementedError

    def set_api_key_quota(self, key: str, quota: QuotaLimits) -> None:
        raise NotImplementedError

    def get_api_key_quota(self, key: str) -> QuotaLimits:
        raise NotImplementedError

    def set_retention_policy(self, org_id: str, policy: RetentionPolicyConfig) -> None:
        raise NotImplementedError

    def get_retention_policy(self, org_id: str) -> Optional[RetentionPolicyConfig]:
        raise NotImplementedError

    def set_residency(self, org_id: str, region: Optional[str]) -> None:
        raise NotImplementedError

    def get_residency(self, org_id: str) -> Optional[str]:
        raise NotImplementedError

    def set_encryption_key(self, org_id: str, key: Optional[str]) -> None:
        raise NotImplementedError

    def get_encryption_key(self, org_id: str) -> Optional[str]:
        raise NotImplementedError

    def set_model_policy(self, org_id: str, policy: ModelPolicy) -> None:
        raise NotImplementedError

    def get_model_policy(self, org_id: str) -> Optional[ModelPolicy]:
        raise NotImplementedError

    def create_policy_bundle(self, bundle: PolicyBundle) -> PolicyBundle:
        raise NotImplementedError

    def list_policy_bundles(self) -> List[PolicyBundle]:
        raise NotImplementedError

    def list_policy_bundle_versions(self, bundle_id: str) -> List[PolicyBundle]:
        raise NotImplementedError

    def get_policy_bundle(self, bundle_id: str, version: Optional[int] = None) -> Optional[PolicyBundle]:
        raise NotImplementedError

    def assign_policy_bundle(self, assignment: PolicyAssignment) -> PolicyAssignment:
        raise NotImplementedError

    def get_policy_assignment(self, org_id: str) -> Optional[PolicyAssignment]:
        raise NotImplementedError

    def create_policy_approval(self, approval: PolicyApproval) -> PolicyApproval:
        raise NotImplementedError

    def get_policy_approval(
        self,
        bundle_id: str,
        version: int,
        org_id: Optional[str] = None,
    ) -> Optional[PolicyApproval]:
        raise NotImplementedError

    def list_policy_approvals(
        self,
        bundle_id: Optional[str] = None,
        status: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> List[PolicyApproval]:
        raise NotImplementedError

    def create_backup_record(self, record: BackupRecord) -> BackupRecord:
        raise NotImplementedError

    def list_backup_records(self) -> List[BackupRecord]:
        raise NotImplementedError

    def get_backup_record(self, backup_id: str) -> Optional[BackupRecord]:
        raise NotImplementedError

    def create_webhook_subscription(self, subscription: WebhookSubscription) -> WebhookSubscription:
        raise NotImplementedError

    def list_webhook_subscriptions(self, org_id: Optional[str] = None) -> List[WebhookSubscription]:
        raise NotImplementedError

    def delete_webhook_subscription(self, subscription_id: str) -> bool:
        raise NotImplementedError

    def set_secret_rotation_policy(self, policy: SecretRotationPolicy) -> SecretRotationPolicy:
        raise NotImplementedError

    def list_secret_rotation_policies(self, org_id: Optional[str] = None) -> List[SecretRotationPolicy]:
        raise NotImplementedError


class SQLiteControlPlane(ControlPlaneBackend):
    def __init__(self, path: str):
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS orgs (
                    org_id TEXT PRIMARY KEY,
                    name TEXT,
                    created_at TEXT,
                    quotas_json TEXT,
                    model_policy_json TEXT,
                    retention_json TEXT,
                    residency TEXT,
                    encryption_key TEXT,
                    policy_bundle_id TEXT,
                    policy_bundle_version INTEGER,
                    policy_overrides_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    name TEXT,
                    created_at TEXT,
                    active INTEGER,
                    is_service_account INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    name TEXT,
                    created_at TEXT,
                    tags_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    project_id TEXT,
                    key TEXT,
                    label TEXT,
                    role TEXT,
                    scopes_json TEXT,
                    created_at TEXT,
                    active INTEGER,
                    expires_at TEXT,
                    rotated_at TEXT,
                    rate_limit_per_minute INTEGER,
                    ip_allowlist_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS project_quotas (
                    project_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    max_runs INTEGER,
                    max_sessions INTEGER,
                    max_tokens INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_key_quotas (
                    key TEXT PRIMARY KEY,
                    org_id TEXT,
                    max_runs INTEGER,
                    max_sessions INTEGER,
                    max_tokens INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_bundles (
                    bundle_id TEXT,
                    version INTEGER,
                    content_json TEXT,
                    description TEXT,
                    created_at TEXT,
                    PRIMARY KEY (bundle_id, version)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_approvals (
                    bundle_id TEXT,
                    version INTEGER,
                    org_id TEXT,
                    status TEXT,
                    submitted_by TEXT,
                    reviewed_by TEXT,
                    submitted_at TEXT,
                    reviewed_at TEXT,
                    notes TEXT,
                    PRIMARY KEY (bundle_id, version, org_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS backups (
                    backup_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    label TEXT,
                    storage_backend TEXT,
                    storage_path TEXT,
                    control_plane_backend TEXT,
                    control_plane_path TEXT,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    url TEXT,
                    event_types_json TEXT,
                    secret TEXT,
                    created_at TEXT,
                    active INTEGER,
                    max_attempts INTEGER,
                    backoff_seconds REAL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS secret_rotation_policies (
                    secret_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    rotation_days INTEGER,
                    last_rotated_at TEXT,
                    created_at TEXT
                )
                """
            )
            self._ensure_column(conn, "api_keys", "expires_at", "TEXT")
            self._ensure_column(conn, "api_keys", "rotated_at", "TEXT")
            self._ensure_column(conn, "api_keys", "rate_limit_per_minute", "INTEGER")
            self._ensure_column(conn, "api_keys", "ip_allowlist_json", "TEXT")
            self._ensure_column(conn, "api_keys", "project_id", "TEXT")
            self._ensure_column(conn, "orgs", "retention_json", "TEXT")
            self._ensure_column(conn, "users", "active", "INTEGER")
            self._ensure_column(conn, "users", "is_service_account", "INTEGER")
            self._ensure_column(conn, "orgs", "residency", "TEXT")
            self._ensure_column(conn, "orgs", "encryption_key", "TEXT")
            self._ensure_column(conn, "orgs", "policy_bundle_id", "TEXT")
            self._ensure_column(conn, "orgs", "policy_bundle_version", "INTEGER")
            self._ensure_column(conn, "orgs", "policy_overrides_json", "TEXT")

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column in existing:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    def ensure_org(self, org_id: str, name: Optional[str] = None) -> Organization:
        existing = self.get_org(org_id)
        if existing:
            return existing
        org = Organization(org_id=org_id, name=name or org_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO orgs (
                    org_id,
                    name,
                    created_at,
                    quotas_json,
                    model_policy_json,
                    retention_json,
                    residency,
                    encryption_key,
                    policy_bundle_id,
                    policy_bundle_version,
                    policy_overrides_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    org.org_id,
                    org.name,
                    org.created_at,
                    json.dumps({}),
                    json.dumps({}),
                    json.dumps({}),
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
        return org

    def get_org(self, org_id: str) -> Optional[Organization]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orgs WHERE org_id = ?", (org_id,)).fetchone()
            if not row:
                return None
            return Organization(
                org_id=row["org_id"],
                name=row["name"],
                created_at=row["created_at"],
                policy_bundle_id=row["policy_bundle_id"],
                policy_bundle_version=row["policy_bundle_version"],
                policy_overrides=json.loads(row["policy_overrides_json"] or "{}"),
            )

    def list_orgs(self) -> List[Organization]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM orgs ORDER BY created_at ASC").fetchall()
            return [
                Organization(
                    org_id=row["org_id"],
                    name=row["name"],
                    created_at=row["created_at"],
                    policy_bundle_id=row["policy_bundle_id"],
                    policy_bundle_version=row["policy_bundle_version"],
                    policy_overrides=json.loads(row["policy_overrides_json"] or "{}"),
                )
                for row in rows
            ]

    def create_project(self, project: Project) -> Project:
        self.ensure_org(project.org_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (project_id, org_id, name, created_at, tags_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    project.org_id,
                    project.name,
                    project.created_at,
                    json.dumps(project.tags),
                ),
            )
        return project

    def list_projects(self, org_id: Optional[str] = None) -> List[Project]:
        with self._connect() as conn:
            if org_id:
                rows = conn.execute("SELECT * FROM projects WHERE org_id = ?", (org_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM projects").fetchall()
            return [
                Project(
                    project_id=row["project_id"],
                    org_id=row["org_id"],
                    name=row["name"],
                    created_at=row["created_at"],
                    tags=json.loads(row["tags_json"] or "{}"),
                )
                for row in rows
            ]

    def get_project(self, project_id: str) -> Optional[Project]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                return None
            return Project(
                project_id=row["project_id"],
                org_id=row["org_id"],
                name=row["name"],
                created_at=row["created_at"],
                tags=json.loads(row["tags_json"] or "{}"),
            )

    def delete_project(self, project_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM project_quotas WHERE project_id = ?", (project_id,))
            return cur.rowcount > 0

    def create_user(self, org_id: str, user: User) -> User:
        self.ensure_org(org_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, org_id, name, created_at, active, is_service_account)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    user.org_id,
                    user.name,
                    user.created_at,
                    1 if user.active else 0,
                    1 if user.is_service_account else 0,
                ),
            )
        return user

    def list_users(self, org_id: Optional[str] = None, active_only: bool = False) -> List[User]:
        with self._connect() as conn:
            if org_id is None:
                rows = conn.execute("SELECT * FROM users").fetchall()
            else:
                rows = conn.execute("SELECT * FROM users WHERE org_id = ?", (org_id,)).fetchall()
            users = [
                User(
                    user_id=row["user_id"],
                    org_id=row["org_id"],
                    name=row["name"],
                    created_at=row["created_at"],
                    active=bool(row["active"]) if row["active"] is not None else True,
                    is_service_account=bool(row["is_service_account"])
                    if row["is_service_account"] is not None
                    else False,
                )
                for row in rows
            ]
            if active_only:
                users = [user for user in users if user.active]
            return users

    def deactivate_user(self, user_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("UPDATE users SET active = 0 WHERE user_id = ?", (user_id,))
            return cur.rowcount > 0

    def create_api_key(self, record: APIKeyRecord) -> APIKeyRecord:
        self.ensure_org(record.org_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO api_keys (
                    key_id, org_id, project_id, key, label, role, scopes_json,
                    created_at, active, expires_at, rotated_at, rate_limit_per_minute, ip_allowlist_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.key_id,
                    record.org_id,
                    record.project_id,
                    record.key,
                    record.label,
                    record.role,
                    json.dumps(record.scopes),
                    record.created_at,
                    1 if record.active else 0,
                    record.expires_at,
                    record.rotated_at,
                    record.rate_limit_per_minute,
                    json.dumps(record.ip_allowlist),
                ),
            )
        return record

    def list_api_keys(self, org_id: Optional[str] = None) -> List[APIKeyRecord]:
        with self._connect() as conn:
            if org_id is None:
                rows = conn.execute("SELECT * FROM api_keys").fetchall()
            else:
                rows = conn.execute("SELECT * FROM api_keys WHERE org_id = ?", (org_id,)).fetchall()
            records = []
            for row in rows:
                records.append(
                    APIKeyRecord(
                        key_id=row["key_id"],
                        org_id=row["org_id"],
                        project_id=row["project_id"],
                        key=row["key"],
                        label=row["label"],
                        role=row["role"] or "developer",
                        scopes=json.loads(row["scopes_json"] or "[]"),
                        created_at=row["created_at"],
                        active=bool(row["active"]),
                        expires_at=row["expires_at"],
                        rotated_at=row["rotated_at"],
                        rate_limit_per_minute=row["rate_limit_per_minute"],
                        ip_allowlist=json.loads(row["ip_allowlist_json"] or "[]"),
                    )
                )
            return records

    def deactivate_api_key(self, key_id: str, rotated_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE api_keys SET active = 0, rotated_at = ? WHERE key_id = ?",
                (rotated_at, key_id),
            )

    def delete_api_key(self, key_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT key FROM api_keys WHERE key_id = ?", (key_id,)).fetchone()
            key_value = row["key"] if row else None
            cur = conn.execute("DELETE FROM api_keys WHERE key_id = ?", (key_id,))
            if key_value:
                conn.execute("DELETE FROM api_key_quotas WHERE key = ?", (key_value,))
            return cur.rowcount > 0

    def set_quota(self, org_id: str, quota: QuotaLimits) -> None:
        self.ensure_org(org_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE orgs SET quotas_json = ? WHERE org_id = ?",
                (json.dumps(asdict(quota)), org_id),
            )

    def get_quota(self, org_id: str) -> QuotaLimits:
        with self._connect() as conn:
            row = conn.execute("SELECT quotas_json FROM orgs WHERE org_id = ?", (org_id,)).fetchone()
            if not row or not row["quotas_json"]:
                return QuotaLimits()
            data = json.loads(row["quotas_json"] or "{}")
            return QuotaLimits(**data)

    def set_project_quota(self, project_id: str, quota: QuotaLimits) -> None:
        with self._connect() as conn:
            org_id = None
            row = conn.execute("SELECT org_id FROM projects WHERE project_id = ?", (project_id,)).fetchone()
            if row:
                org_id = row["org_id"]
            conn.execute(
                """
                INSERT OR REPLACE INTO project_quotas (project_id, org_id, max_runs, max_sessions, max_tokens)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    org_id,
                    quota.max_runs,
                    quota.max_sessions,
                    quota.max_tokens,
                ),
            )

    def get_project_quota(self, project_id: str) -> QuotaLimits:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT max_runs, max_sessions, max_tokens FROM project_quotas WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                return QuotaLimits()
            return QuotaLimits(max_runs=row[0], max_sessions=row[1], max_tokens=row[2])

    def set_api_key_quota(self, key: str, quota: QuotaLimits) -> None:
        with self._connect() as conn:
            row = conn.execute("SELECT org_id FROM api_keys WHERE key = ?", (key,)).fetchone()
            org_id = row["org_id"] if row else None
            conn.execute(
                """
                INSERT OR REPLACE INTO api_key_quotas (key, org_id, max_runs, max_sessions, max_tokens)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    key,
                    org_id,
                    quota.max_runs,
                    quota.max_sessions,
                    quota.max_tokens,
                ),
            )

    def get_api_key_quota(self, key: str) -> QuotaLimits:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT max_runs, max_sessions, max_tokens FROM api_key_quotas WHERE key = ?",
                (key,),
            ).fetchone()
            if not row:
                return QuotaLimits()
            return QuotaLimits(max_runs=row[0], max_sessions=row[1], max_tokens=row[2])

    def set_retention_policy(self, org_id: str, policy: RetentionPolicyConfig) -> None:
        self.ensure_org(org_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE orgs SET retention_json = ? WHERE org_id = ?",
                (json.dumps(asdict(policy)), org_id),
            )

    def get_retention_policy(self, org_id: str) -> Optional[RetentionPolicyConfig]:
        with self._connect() as conn:
            row = conn.execute("SELECT retention_json FROM orgs WHERE org_id = ?", (org_id,)).fetchone()
            if not row or not row["retention_json"]:
                return None
            data = json.loads(row["retention_json"] or "{}")
            return RetentionPolicyConfig(**data)

    def set_residency(self, org_id: str, region: Optional[str]) -> None:
        self.ensure_org(org_id)
        with self._connect() as conn:
            conn.execute("UPDATE orgs SET residency = ? WHERE org_id = ?", (region, org_id))

    def get_residency(self, org_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT residency FROM orgs WHERE org_id = ?", (org_id,)).fetchone()
            if not row:
                return None
            return row["residency"]

    def set_encryption_key(self, org_id: str, key: Optional[str]) -> None:
        self.ensure_org(org_id)
        with self._connect() as conn:
            conn.execute("UPDATE orgs SET encryption_key = ? WHERE org_id = ?", (key, org_id))

    def get_encryption_key(self, org_id: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT encryption_key FROM orgs WHERE org_id = ?", (org_id,)).fetchone()
            if not row:
                return None
            return row["encryption_key"]

    def set_model_policy(self, org_id: str, policy: ModelPolicy) -> None:
        self.ensure_org(org_id)
        with self._connect() as conn:
            conn.execute(
                "UPDATE orgs SET model_policy_json = ? WHERE org_id = ?",
                (json.dumps(asdict(policy)), org_id),
            )

    def get_model_policy(self, org_id: str) -> Optional[ModelPolicy]:
        with self._connect() as conn:
            row = conn.execute("SELECT model_policy_json FROM orgs WHERE org_id = ?", (org_id,)).fetchone()
            if not row or not row["model_policy_json"]:
                return None
            data = json.loads(row["model_policy_json"] or "{}")
            return ModelPolicy(**data)

    def create_policy_bundle(self, bundle: PolicyBundle) -> PolicyBundle:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT MAX(version) AS max_version FROM policy_bundles WHERE bundle_id = ?",
                (bundle.bundle_id,),
            ).fetchone()
            next_version = bundle.version or ((existing["max_version"] or 0) + 1)
            conn.execute(
                """
                INSERT INTO policy_bundles (bundle_id, version, content_json, description, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    bundle.bundle_id,
                    next_version,
                    json.dumps(bundle.content),
                    bundle.description,
                    bundle.created_at,
                ),
            )
        return PolicyBundle(
            bundle_id=bundle.bundle_id,
            version=next_version,
            content=bundle.content,
            description=bundle.description,
            created_at=bundle.created_at,
        )

    def list_policy_bundles(self) -> List[PolicyBundle]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT pb.bundle_id, pb.version, pb.content_json, pb.description, pb.created_at
                FROM policy_bundles pb
                JOIN (
                    SELECT bundle_id, MAX(version) AS max_version
                    FROM policy_bundles
                    GROUP BY bundle_id
                ) latest
                ON pb.bundle_id = latest.bundle_id AND pb.version = latest.max_version
                ORDER BY pb.bundle_id ASC
                """
            ).fetchall()
            return [
                PolicyBundle(
                    bundle_id=row["bundle_id"],
                    version=row["version"],
                    content=json.loads(row["content_json"] or "{}"),
                    description=row["description"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def list_policy_bundle_versions(self, bundle_id: str) -> List[PolicyBundle]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT bundle_id, version, content_json, description, created_at
                FROM policy_bundles
                WHERE bundle_id = ?
                ORDER BY version ASC
                """,
                (bundle_id,),
            ).fetchall()
            return [
                PolicyBundle(
                    bundle_id=row["bundle_id"],
                    version=row["version"],
                    content=json.loads(row["content_json"] or "{}"),
                    description=row["description"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def get_policy_bundle(self, bundle_id: str, version: Optional[int] = None) -> Optional[PolicyBundle]:
        with self._connect() as conn:
            if version is None:
                row = conn.execute(
                    """
                    SELECT bundle_id, version, content_json, description, created_at
                    FROM policy_bundles
                    WHERE bundle_id = ?
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (bundle_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT bundle_id, version, content_json, description, created_at
                    FROM policy_bundles
                    WHERE bundle_id = ? AND version = ?
                    """,
                    (bundle_id, version),
                ).fetchone()
            if not row:
                return None
            return PolicyBundle(
                bundle_id=row["bundle_id"],
                version=row["version"],
                content=json.loads(row["content_json"] or "{}"),
                description=row["description"],
                created_at=row["created_at"],
            )

    def assign_policy_bundle(self, assignment: PolicyAssignment) -> PolicyAssignment:
        self.ensure_org(assignment.org_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE orgs
                SET policy_bundle_id = ?, policy_bundle_version = ?, policy_overrides_json = ?
                WHERE org_id = ?
                """,
                (
                    assignment.bundle_id,
                    assignment.version,
                    json.dumps(assignment.overrides),
                    assignment.org_id,
                ),
            )
        return assignment

    def get_policy_assignment(self, org_id: str) -> Optional[PolicyAssignment]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT policy_bundle_id, policy_bundle_version, policy_overrides_json
                FROM orgs
                WHERE org_id = ?
                """,
                (org_id,),
            ).fetchone()
            if not row or not row["policy_bundle_id"] or row["policy_bundle_version"] is None:
                return None
            return PolicyAssignment(
                org_id=org_id,
                bundle_id=row["policy_bundle_id"],
                version=row["policy_bundle_version"],
                overrides=json.loads(row["policy_overrides_json"] or "{}"),
            )

    def create_policy_approval(self, approval: PolicyApproval) -> PolicyApproval:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO policy_approvals (
                    bundle_id, version, org_id, status, submitted_by, reviewed_by,
                    submitted_at, reviewed_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.bundle_id,
                    approval.version,
                    approval.org_id,
                    approval.status,
                    approval.submitted_by,
                    approval.reviewed_by,
                    approval.submitted_at,
                    approval.reviewed_at,
                    approval.notes,
                ),
            )
        return approval

    def get_policy_approval(
        self,
        bundle_id: str,
        version: int,
        org_id: Optional[str] = None,
    ) -> Optional[PolicyApproval]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM policy_approvals
                WHERE bundle_id = ? AND version = ? AND org_id IS ?
                """,
                (bundle_id, version, org_id),
            ).fetchone()
            if not row:
                return None
            return PolicyApproval(
                bundle_id=row["bundle_id"],
                version=row["version"],
                status=row["status"],
                submitted_by=row["submitted_by"],
                reviewed_by=row["reviewed_by"],
                submitted_at=row["submitted_at"],
                reviewed_at=row["reviewed_at"],
                notes=row["notes"],
                org_id=row["org_id"],
            )

    def list_policy_approvals(
        self,
        bundle_id: Optional[str] = None,
        status: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> List[PolicyApproval]:
        query = "SELECT * FROM policy_approvals"
        conditions = []
        params: List[object] = []
        if bundle_id:
            conditions.append("bundle_id = ?")
            params.append(bundle_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if org_id is not None:
            conditions.append("org_id IS ?")
            params.append(org_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY submitted_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                PolicyApproval(
                    bundle_id=row["bundle_id"],
                    version=row["version"],
                    status=row["status"],
                    submitted_by=row["submitted_by"],
                    reviewed_by=row["reviewed_by"],
                    submitted_at=row["submitted_at"],
                    reviewed_at=row["reviewed_at"],
                    notes=row["notes"],
                    org_id=row["org_id"],
                )
                for row in rows
            ]

    def create_backup_record(self, record: BackupRecord) -> BackupRecord:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO backups (
                    backup_id,
                    created_at,
                    label,
                    storage_backend,
                    storage_path,
                    control_plane_backend,
                    control_plane_path,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.backup_id,
                    record.created_at,
                    record.label,
                    record.storage_backend,
                    record.storage_path,
                    record.control_plane_backend,
                    record.control_plane_path,
                    json.dumps(record.metadata),
                ),
            )
        return record

    def list_backup_records(self) -> List[BackupRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM backups ORDER BY created_at DESC"
            ).fetchall()
            return [
                BackupRecord(
                    backup_id=row["backup_id"],
                    created_at=row["created_at"],
                    label=row["label"],
                    storage_backend=row["storage_backend"],
                    storage_path=row["storage_path"],
                    control_plane_backend=row["control_plane_backend"],
                    control_plane_path=row["control_plane_path"],
                    metadata=json.loads(row["metadata_json"] or "{}"),
                )
                for row in rows
            ]

    def get_backup_record(self, backup_id: str) -> Optional[BackupRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM backups WHERE backup_id = ?",
                (backup_id,),
            ).fetchone()
            if not row:
                return None
            return BackupRecord(
                backup_id=row["backup_id"],
                created_at=row["created_at"],
                label=row["label"],
                storage_backend=row["storage_backend"],
                storage_path=row["storage_path"],
                control_plane_backend=row["control_plane_backend"],
                control_plane_path=row["control_plane_path"],
                metadata=json.loads(row["metadata_json"] or "{}"),
            )

    def create_webhook_subscription(self, subscription: WebhookSubscription) -> WebhookSubscription:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO webhook_subscriptions (
                    subscription_id, org_id, url, event_types_json, secret, created_at,
                    active, max_attempts, backoff_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    subscription.subscription_id,
                    subscription.org_id,
                    subscription.url,
                    json.dumps(subscription.event_types),
                    subscription.secret,
                    subscription.created_at,
                    1 if subscription.active else 0,
                    subscription.max_attempts,
                    subscription.backoff_seconds,
                ),
            )
        return subscription

    def list_webhook_subscriptions(self, org_id: Optional[str] = None) -> List[WebhookSubscription]:
        with self._connect() as conn:
            if org_id:
                rows = conn.execute(
                    "SELECT * FROM webhook_subscriptions WHERE org_id = ?",
                    (org_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM webhook_subscriptions").fetchall()
            return [
                WebhookSubscription(
                    subscription_id=row["subscription_id"],
                    org_id=row["org_id"],
                    url=row["url"],
                    event_types=json.loads(row["event_types_json"] or "[]"),
                    secret=row["secret"],
                    created_at=row["created_at"],
                    active=bool(row["active"]),
                    max_attempts=row["max_attempts"] or 3,
                    backoff_seconds=row["backoff_seconds"] or 1.0,
                )
                for row in rows
            ]

    def delete_webhook_subscription(self, subscription_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM webhook_subscriptions WHERE subscription_id = ?",
                (subscription_id,),
            )
            return cur.rowcount > 0

    def set_secret_rotation_policy(self, policy: SecretRotationPolicy) -> SecretRotationPolicy:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO secret_rotation_policies (
                    secret_id, org_id, rotation_days, last_rotated_at, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    policy.secret_id,
                    policy.org_id,
                    policy.rotation_days,
                    policy.last_rotated_at,
                    policy.created_at,
                ),
            )
        return policy

    def list_secret_rotation_policies(self, org_id: Optional[str] = None) -> List[SecretRotationPolicy]:
        with self._connect() as conn:
            if org_id:
                rows = conn.execute(
                    "SELECT * FROM secret_rotation_policies WHERE org_id = ?",
                    (org_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM secret_rotation_policies").fetchall()
            return [
                SecretRotationPolicy(
                    secret_id=row["secret_id"],
                    org_id=row["org_id"],
                    rotation_days=row["rotation_days"],
                    last_rotated_at=row["last_rotated_at"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]


class PostgresControlPlane(ControlPlaneBackend):
    def __init__(self, dsn: str, initialize_schema: bool = True):
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgresControlPlane")
        self.dsn = dsn
        self._conn = psycopg.connect(dsn)
        if initialize_schema:
            self._init_db()

    def _init_db(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS orgs (
                    org_id TEXT PRIMARY KEY,
                    name TEXT,
                    created_at TEXT,
                    quotas_json JSONB,
                    model_policy_json JSONB,
                    retention_json JSONB,
                    residency TEXT,
                    encryption_key TEXT,
                    policy_bundle_id TEXT,
                    policy_bundle_version INTEGER,
                    policy_overrides_json JSONB
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    name TEXT,
                    created_at TEXT,
                    active BOOLEAN,
                    is_service_account BOOLEAN
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    name TEXT,
                    created_at TEXT,
                    tags_json JSONB
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    project_id TEXT,
                    key TEXT,
                    label TEXT,
                    role TEXT,
                    scopes_json JSONB,
                    created_at TEXT,
                    active BOOLEAN,
                    expires_at TEXT,
                    rotated_at TEXT,
                    rate_limit_per_minute INTEGER,
                    ip_allowlist_json JSONB
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS project_quotas (
                    project_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    max_runs INTEGER,
                    max_sessions INTEGER,
                    max_tokens INTEGER
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS api_key_quotas (
                    key TEXT PRIMARY KEY,
                    org_id TEXT,
                    max_runs INTEGER,
                    max_sessions INTEGER,
                    max_tokens INTEGER
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_bundles (
                    bundle_id TEXT,
                    version INTEGER,
                    content_json JSONB,
                    description TEXT,
                    created_at TEXT,
                    PRIMARY KEY (bundle_id, version)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_approvals (
                    bundle_id TEXT,
                    version INTEGER,
                    org_id TEXT,
                    status TEXT,
                    submitted_by TEXT,
                    reviewed_by TEXT,
                    submitted_at TEXT,
                    reviewed_at TEXT,
                    notes TEXT,
                    PRIMARY KEY (bundle_id, version, org_id)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS backups (
                    backup_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    label TEXT,
                    storage_backend TEXT,
                    storage_path TEXT,
                    control_plane_backend TEXT,
                    control_plane_path TEXT,
                    metadata_json JSONB
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_subscriptions (
                    subscription_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    url TEXT,
                    event_types_json JSONB,
                    secret TEXT,
                    created_at TEXT,
                    active BOOLEAN,
                    max_attempts INTEGER,
                    backoff_seconds REAL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS secret_rotation_policies (
                    secret_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    rotation_days INTEGER,
                    last_rotated_at TEXT,
                    created_at TEXT
                );
                """
            )
        self._conn.commit()

    def ensure_org(self, org_id: str, name: Optional[str] = None) -> Organization:
        existing = self.get_org(org_id)
        if existing:
            return existing
        org = Organization(org_id=org_id, name=name or org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orgs (
                    org_id,
                    name,
                    created_at,
                    quotas_json,
                    model_policy_json,
                    retention_json,
                    residency,
                    encryption_key,
                    policy_bundle_id,
                    policy_bundle_version,
                    policy_overrides_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    org.org_id,
                    org.name,
                    org.created_at,
                    json.dumps({}),
                    json.dumps({}),
                    json.dumps({}),
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )
        self._conn.commit()
        return org

    def get_org(self, org_id: str) -> Optional[Organization]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM orgs WHERE org_id = %s", (org_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Organization(
                org_id=row[0],
                name=row[1],
                created_at=row[2],
                policy_bundle_id=row[8],
                policy_bundle_version=row[9],
                policy_overrides=row[10] or {},
            )

    def list_orgs(self) -> List[Organization]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM orgs ORDER BY created_at ASC")
            rows = cur.fetchall()
            return [
                Organization(
                    org_id=row[0],
                    name=row[1],
                    created_at=row[2],
                    policy_bundle_id=row[8],
                    policy_bundle_version=row[9],
                    policy_overrides=row[10] or {},
                )
                for row in rows
            ]

    def create_project(self, project: Project) -> Project:
        self.ensure_org(project.org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO projects (project_id, org_id, name, created_at, tags_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    project.project_id,
                    project.org_id,
                    project.name,
                    project.created_at,
                    json.dumps(project.tags),
                ),
            )
        self._conn.commit()
        return project

    def list_projects(self, org_id: Optional[str] = None) -> List[Project]:
        with self._conn.cursor() as cur:
            if org_id:
                cur.execute("SELECT * FROM projects WHERE org_id = %s", (org_id,))
            else:
                cur.execute("SELECT * FROM projects")
            rows = cur.fetchall()
            return [
                Project(
                    project_id=row[0],
                    org_id=row[1],
                    name=row[2],
                    created_at=row[3],
                    tags=row[4] or {},
                )
                for row in rows
            ]

    def get_project(self, project_id: str) -> Optional[Project]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Project(
                project_id=row[0],
                org_id=row[1],
                name=row[2],
                created_at=row[3],
                tags=row[4] or {},
            )

    def delete_project(self, project_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM project_quotas WHERE project_id = %s", (project_id,))
            cur.execute("DELETE FROM projects WHERE project_id = %s", (project_id,))
            deleted = cur.rowcount > 0
        self._conn.commit()
        return deleted

    def create_user(self, org_id: str, user: User) -> User:
        self.ensure_org(org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, org_id, name, created_at, active, is_service_account)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user.user_id,
                    user.org_id,
                    user.name,
                    user.created_at,
                    user.active,
                    user.is_service_account,
                ),
            )
        self._conn.commit()
        return user

    def list_users(self, org_id: Optional[str] = None, active_only: bool = False) -> List[User]:
        with self._conn.cursor() as cur:
            if org_id is None:
                cur.execute("SELECT * FROM users")
                rows = cur.fetchall()
            else:
                cur.execute("SELECT * FROM users WHERE org_id = %s", (org_id,))
                rows = cur.fetchall()
            users = [
                User(
                    user_id=row[0],
                    org_id=row[1],
                    name=row[2],
                    created_at=row[3],
                    active=bool(row[4]) if row[4] is not None else True,
                    is_service_account=bool(row[5]) if row[5] is not None else False,
                )
                for row in rows
            ]
            if active_only:
                users = [user for user in users if user.active]
            return users

    def deactivate_user(self, user_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute("UPDATE users SET active = FALSE WHERE user_id = %s", (user_id,))
            updated = cur.rowcount > 0
        self._conn.commit()
        return updated

    def create_api_key(self, record: APIKeyRecord) -> APIKeyRecord:
        self.ensure_org(record.org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_keys (
                    key_id, org_id, project_id, key, label, role, scopes_json,
                    created_at, active, expires_at, rotated_at, rate_limit_per_minute, ip_allowlist_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.key_id,
                    record.org_id,
                    record.project_id,
                    record.key,
                    record.label,
                    record.role,
                    json.dumps(record.scopes),
                    record.created_at,
                    record.active,
                    record.expires_at,
                    record.rotated_at,
                    record.rate_limit_per_minute,
                    json.dumps(record.ip_allowlist),
                ),
            )
        self._conn.commit()
        return record

    def list_api_keys(self, org_id: Optional[str] = None) -> List[APIKeyRecord]:
        with self._conn.cursor() as cur:
            if org_id is None:
                cur.execute("SELECT * FROM api_keys")
                rows = cur.fetchall()
            else:
                cur.execute("SELECT * FROM api_keys WHERE org_id = %s", (org_id,))
                rows = cur.fetchall()
            records = []
            for row in rows:
                records.append(
                    APIKeyRecord(
                        key_id=row[0],
                        org_id=row[1],
                        project_id=row[2],
                        key=row[3],
                        label=row[4],
                        role=row[5] or "developer",
                        scopes=json.loads(row[6] or "[]"),
                        created_at=row[7],
                        active=bool(row[8]),
                        expires_at=row[9],
                        rotated_at=row[10],
                        rate_limit_per_minute=row[11],
                        ip_allowlist=json.loads(row[12] or "[]"),
                    )
                )
            return records

    def deactivate_api_key(self, key_id: str, rotated_at: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE api_keys SET active = FALSE, rotated_at = %s WHERE key_id = %s",
                (rotated_at, key_id),
            )
        self._conn.commit()

    def delete_api_key(self, key_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute("SELECT key FROM api_keys WHERE key_id = %s", (key_id,))
            row = cur.fetchone()
            key_value = row[0] if row else None
            cur.execute("DELETE FROM api_keys WHERE key_id = %s", (key_id,))
            deleted = cur.rowcount > 0
            if key_value:
                cur.execute("DELETE FROM api_key_quotas WHERE key = %s", (key_value,))
        self._conn.commit()
        return deleted

    def set_quota(self, org_id: str, quota: QuotaLimits) -> None:
        self.ensure_org(org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE orgs SET quotas_json = %s WHERE org_id = %s",
                (json.dumps(asdict(quota)), org_id),
            )
        self._conn.commit()

    def get_quota(self, org_id: str) -> QuotaLimits:
        with self._conn.cursor() as cur:
            cur.execute("SELECT quotas_json FROM orgs WHERE org_id = %s", (org_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                return QuotaLimits()
            return QuotaLimits(**row[0])

    def set_project_quota(self, project_id: str, quota: QuotaLimits) -> None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT org_id FROM projects WHERE project_id = %s", (project_id,))
            row = cur.fetchone()
            org_id = row[0] if row else None
            cur.execute(
                """
                INSERT INTO project_quotas (project_id, org_id, max_runs, max_sessions, max_tokens)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (project_id)
                DO UPDATE SET
                    org_id = EXCLUDED.org_id,
                    max_runs = EXCLUDED.max_runs,
                    max_sessions = EXCLUDED.max_sessions,
                    max_tokens = EXCLUDED.max_tokens
                """,
                (
                    project_id,
                    org_id,
                    quota.max_runs,
                    quota.max_sessions,
                    quota.max_tokens,
                ),
            )
        self._conn.commit()

    def get_project_quota(self, project_id: str) -> QuotaLimits:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT max_runs, max_sessions, max_tokens FROM project_quotas WHERE project_id = %s",
                (project_id,),
            )
            row = cur.fetchone()
            if not row:
                return QuotaLimits()
            return QuotaLimits(max_runs=row[0], max_sessions=row[1], max_tokens=row[2])

    def set_api_key_quota(self, key: str, quota: QuotaLimits) -> None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT org_id FROM api_keys WHERE key = %s", (key,))
            row = cur.fetchone()
            org_id = row[0] if row else None
            cur.execute(
                """
                INSERT INTO api_key_quotas (key, org_id, max_runs, max_sessions, max_tokens)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (key)
                DO UPDATE SET
                    org_id = EXCLUDED.org_id,
                    max_runs = EXCLUDED.max_runs,
                    max_sessions = EXCLUDED.max_sessions,
                    max_tokens = EXCLUDED.max_tokens
                """,
                (
                    key,
                    org_id,
                    quota.max_runs,
                    quota.max_sessions,
                    quota.max_tokens,
                ),
            )
        self._conn.commit()

    def get_api_key_quota(self, key: str) -> QuotaLimits:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT max_runs, max_sessions, max_tokens FROM api_key_quotas WHERE key = %s",
                (key,),
            )
            row = cur.fetchone()
            if not row:
                return QuotaLimits()
            return QuotaLimits(max_runs=row[0], max_sessions=row[1], max_tokens=row[2])

    def set_retention_policy(self, org_id: str, policy: RetentionPolicyConfig) -> None:
        self.ensure_org(org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE orgs SET retention_json = %s WHERE org_id = %s",
                (json.dumps(asdict(policy)), org_id),
            )
        self._conn.commit()

    def get_retention_policy(self, org_id: str) -> Optional[RetentionPolicyConfig]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT retention_json FROM orgs WHERE org_id = %s", (org_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            return RetentionPolicyConfig(**row[0])

    def set_residency(self, org_id: str, region: Optional[str]) -> None:
        self.ensure_org(org_id)
        with self._conn.cursor() as cur:
            cur.execute("UPDATE orgs SET residency = %s WHERE org_id = %s", (region, org_id))
        self._conn.commit()

    def get_residency(self, org_id: str) -> Optional[str]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT residency FROM orgs WHERE org_id = %s", (org_id,))
            row = cur.fetchone()
            if not row:
                return None
            return row[0]

    def set_encryption_key(self, org_id: str, key: Optional[str]) -> None:
        self.ensure_org(org_id)
        with self._conn.cursor() as cur:
            cur.execute("UPDATE orgs SET encryption_key = %s WHERE org_id = %s", (key, org_id))
        self._conn.commit()

    def get_encryption_key(self, org_id: str) -> Optional[str]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT encryption_key FROM orgs WHERE org_id = %s", (org_id,))
            row = cur.fetchone()
            if not row:
                return None
            return row[0]

    def set_model_policy(self, org_id: str, policy: ModelPolicy) -> None:
        self.ensure_org(org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE orgs SET model_policy_json = %s WHERE org_id = %s",
                (json.dumps(asdict(policy)), org_id),
            )
        self._conn.commit()

    def get_model_policy(self, org_id: str) -> Optional[ModelPolicy]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT model_policy_json FROM orgs WHERE org_id = %s", (org_id,))
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            return ModelPolicy(**row[0])

    def create_policy_bundle(self, bundle: PolicyBundle) -> PolicyBundle:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(version) FROM policy_bundles WHERE bundle_id = %s",
                (bundle.bundle_id,),
            )
            max_version = cur.fetchone()[0] or 0
            next_version = bundle.version or (max_version + 1)
            cur.execute(
                """
                INSERT INTO policy_bundles (bundle_id, version, content_json, description, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    bundle.bundle_id,
                    next_version,
                    json.dumps(bundle.content),
                    bundle.description,
                    bundle.created_at,
                ),
            )
        self._conn.commit()
        return PolicyBundle(
            bundle_id=bundle.bundle_id,
            version=next_version,
            content=bundle.content,
            description=bundle.description,
            created_at=bundle.created_at,
        )

    def list_policy_bundles(self) -> List[PolicyBundle]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT pb.bundle_id, pb.version, pb.content_json, pb.description, pb.created_at
                FROM policy_bundles pb
                JOIN (
                    SELECT bundle_id, MAX(version) AS max_version
                    FROM policy_bundles
                    GROUP BY bundle_id
                ) latest
                ON pb.bundle_id = latest.bundle_id AND pb.version = latest.max_version
                ORDER BY pb.bundle_id ASC
                """
            )
            rows = cur.fetchall()
            return [
                PolicyBundle(
                    bundle_id=row[0],
                    version=row[1],
                    content=row[2] or {},
                    description=row[3],
                    created_at=row[4],
                )
                for row in rows
            ]

    def list_policy_bundle_versions(self, bundle_id: str) -> List[PolicyBundle]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT bundle_id, version, content_json, description, created_at
                FROM policy_bundles
                WHERE bundle_id = %s
                ORDER BY version ASC
                """,
                (bundle_id,),
            )
            rows = cur.fetchall()
            return [
                PolicyBundle(
                    bundle_id=row[0],
                    version=row[1],
                    content=row[2] or {},
                    description=row[3],
                    created_at=row[4],
                )
                for row in rows
            ]

    def get_policy_bundle(self, bundle_id: str, version: Optional[int] = None) -> Optional[PolicyBundle]:
        with self._conn.cursor() as cur:
            if version is None:
                cur.execute(
                    """
                    SELECT bundle_id, version, content_json, description, created_at
                    FROM policy_bundles
                    WHERE bundle_id = %s
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (bundle_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT bundle_id, version, content_json, description, created_at
                    FROM policy_bundles
                    WHERE bundle_id = %s AND version = %s
                    """,
                    (bundle_id, version),
                )
            row = cur.fetchone()
            if not row:
                return None
            return PolicyBundle(
                bundle_id=row[0],
                version=row[1],
                content=row[2] or {},
                description=row[3],
                created_at=row[4],
            )

    def assign_policy_bundle(self, assignment: PolicyAssignment) -> PolicyAssignment:
        self.ensure_org(assignment.org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE orgs
                SET policy_bundle_id = %s, policy_bundle_version = %s, policy_overrides_json = %s
                WHERE org_id = %s
                """,
                (
                    assignment.bundle_id,
                    assignment.version,
                    json.dumps(assignment.overrides),
                    assignment.org_id,
                ),
            )
        self._conn.commit()
        return assignment

    def get_policy_assignment(self, org_id: str) -> Optional[PolicyAssignment]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT policy_bundle_id, policy_bundle_version, policy_overrides_json
                FROM orgs
                WHERE org_id = %s
                """,
                (org_id,),
            )
            row = cur.fetchone()
            if not row or not row[0] or row[1] is None:
                return None
            return PolicyAssignment(
                org_id=org_id,
                bundle_id=row[0],
                version=row[1],
                overrides=row[2] or {},
            )

    def create_policy_approval(self, approval: PolicyApproval) -> PolicyApproval:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO policy_approvals (
                    bundle_id, version, org_id, status, submitted_by, reviewed_by,
                    submitted_at, reviewed_at, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (bundle_id, version, org_id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    submitted_by = EXCLUDED.submitted_by,
                    reviewed_by = EXCLUDED.reviewed_by,
                    submitted_at = EXCLUDED.submitted_at,
                    reviewed_at = EXCLUDED.reviewed_at,
                    notes = EXCLUDED.notes
                """,
                (
                    approval.bundle_id,
                    approval.version,
                    approval.org_id,
                    approval.status,
                    approval.submitted_by,
                    approval.reviewed_by,
                    approval.submitted_at,
                    approval.reviewed_at,
                    approval.notes,
                ),
            )
        self._conn.commit()
        return approval

    def get_policy_approval(
        self,
        bundle_id: str,
        version: int,
        org_id: Optional[str] = None,
    ) -> Optional[PolicyApproval]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT bundle_id, version, org_id, status, submitted_by, reviewed_by,
                       submitted_at, reviewed_at, notes
                FROM policy_approvals
                WHERE bundle_id = %s AND version = %s AND org_id IS NOT DISTINCT FROM %s
                """,
                (bundle_id, version, org_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return PolicyApproval(
                bundle_id=row[0],
                version=row[1],
                org_id=row[2],
                status=row[3],
                submitted_by=row[4],
                reviewed_by=row[5],
                submitted_at=row[6],
                reviewed_at=row[7],
                notes=row[8],
            )

    def list_policy_approvals(
        self,
        bundle_id: Optional[str] = None,
        status: Optional[str] = None,
        org_id: Optional[str] = None,
    ) -> List[PolicyApproval]:
        query = "SELECT bundle_id, version, org_id, status, submitted_by, reviewed_by, submitted_at, reviewed_at, notes FROM policy_approvals"
        conditions = []
        params: List[object] = []
        if bundle_id:
            conditions.append("bundle_id = %s")
            params.append(bundle_id)
        if status:
            conditions.append("status = %s")
            params.append(status)
        if org_id is not None:
            conditions.append("org_id IS NOT DISTINCT FROM %s")
            params.append(org_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY submitted_at DESC"
        with self._conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            return [
                PolicyApproval(
                    bundle_id=row[0],
                    version=row[1],
                    org_id=row[2],
                    status=row[3],
                    submitted_by=row[4],
                    reviewed_by=row[5],
                    submitted_at=row[6],
                    reviewed_at=row[7],
                    notes=row[8],
                )
                for row in rows
            ]

    def create_backup_record(self, record: BackupRecord) -> BackupRecord:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO backups (
                    backup_id,
                    created_at,
                    label,
                    storage_backend,
                    storage_path,
                    control_plane_backend,
                    control_plane_path,
                    metadata_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.backup_id,
                    record.created_at,
                    record.label,
                    record.storage_backend,
                    record.storage_path,
                    record.control_plane_backend,
                    record.control_plane_path,
                    json.dumps(record.metadata),
                ),
            )
        self._conn.commit()
        return record

    def list_backup_records(self) -> List[BackupRecord]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM backups ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [
                BackupRecord(
                    backup_id=row[0],
                    created_at=row[1],
                    label=row[2],
                    storage_backend=row[3],
                    storage_path=row[4],
                    control_plane_backend=row[5],
                    control_plane_path=row[6],
                    metadata=row[7] or {},
                )
                for row in rows
            ]

    def get_backup_record(self, backup_id: str) -> Optional[BackupRecord]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM backups WHERE backup_id = %s", (backup_id,))
            row = cur.fetchone()
            if not row:
                return None
            return BackupRecord(
                backup_id=row[0],
                created_at=row[1],
                label=row[2],
                storage_backend=row[3],
                storage_path=row[4],
                control_plane_backend=row[5],
                control_plane_path=row[6],
                metadata=row[7] or {},
            )

    def create_webhook_subscription(self, subscription: WebhookSubscription) -> WebhookSubscription:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO webhook_subscriptions (
                    subscription_id, org_id, url, event_types_json, secret, created_at,
                    active, max_attempts, backoff_seconds
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    subscription.subscription_id,
                    subscription.org_id,
                    subscription.url,
                    json.dumps(subscription.event_types),
                    subscription.secret,
                    subscription.created_at,
                    subscription.active,
                    subscription.max_attempts,
                    subscription.backoff_seconds,
                ),
            )
        self._conn.commit()
        return subscription

    def list_webhook_subscriptions(self, org_id: Optional[str] = None) -> List[WebhookSubscription]:
        with self._conn.cursor() as cur:
            if org_id:
                cur.execute("SELECT * FROM webhook_subscriptions WHERE org_id = %s", (org_id,))
            else:
                cur.execute("SELECT * FROM webhook_subscriptions")
            rows = cur.fetchall()
            return [
                WebhookSubscription(
                    subscription_id=row[0],
                    org_id=row[1],
                    url=row[2],
                    event_types=row[3] or [],
                    secret=row[4],
                    created_at=row[5],
                    active=bool(row[6]),
                    max_attempts=row[7] or 3,
                    backoff_seconds=row[8] or 1.0,
                )
                for row in rows
            ]

    def delete_webhook_subscription(self, subscription_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM webhook_subscriptions WHERE subscription_id = %s",
                (subscription_id,),
            )
            removed = cur.rowcount > 0
        self._conn.commit()
        return removed

    def set_secret_rotation_policy(self, policy: SecretRotationPolicy) -> SecretRotationPolicy:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO secret_rotation_policies (
                    secret_id, org_id, rotation_days, last_rotated_at, created_at
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (secret_id)
                DO UPDATE SET org_id = EXCLUDED.org_id,
                    rotation_days = EXCLUDED.rotation_days,
                    last_rotated_at = EXCLUDED.last_rotated_at
                """,
                (
                    policy.secret_id,
                    policy.org_id,
                    policy.rotation_days,
                    policy.last_rotated_at,
                    policy.created_at,
                ),
            )
        self._conn.commit()
        return policy

    def list_secret_rotation_policies(self, org_id: Optional[str] = None) -> List[SecretRotationPolicy]:
        with self._conn.cursor() as cur:
            if org_id:
                cur.execute(
                    "SELECT * FROM secret_rotation_policies WHERE org_id = %s",
                    (org_id,),
                )
            else:
                cur.execute("SELECT * FROM secret_rotation_policies")
            rows = cur.fetchall()
            return [
                SecretRotationPolicy(
                    secret_id=row[0],
                    org_id=row[1],
                    rotation_days=row[2],
                    last_rotated_at=row[3],
                    created_at=row[4],
                )
                for row in rows
            ]
