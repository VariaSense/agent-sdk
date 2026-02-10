"""Control plane storage for orgs, users, API keys, quotas, and model policies."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import List, Optional

from agent_sdk.server.multi_tenant import (
    Organization,
    User,
    APIKeyRecord,
    QuotaLimits,
    RetentionPolicyConfig,
    ModelPolicy,
)

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

    def create_user(self, org_id: str, user: User) -> User:
        raise NotImplementedError

    def list_users(self, org_id: Optional[str] = None) -> List[User]:
        raise NotImplementedError

    def create_api_key(self, record: APIKeyRecord) -> APIKeyRecord:
        raise NotImplementedError

    def list_api_keys(self, org_id: Optional[str] = None) -> List[APIKeyRecord]:
        raise NotImplementedError

    def deactivate_api_key(self, key_id: str, rotated_at: str) -> None:
        raise NotImplementedError

    def set_quota(self, org_id: str, quota: QuotaLimits) -> None:
        raise NotImplementedError

    def get_quota(self, org_id: str) -> QuotaLimits:
        raise NotImplementedError

    def set_retention_policy(self, org_id: str, policy: RetentionPolicyConfig) -> None:
        raise NotImplementedError

    def get_retention_policy(self, org_id: str) -> Optional[RetentionPolicyConfig]:
        raise NotImplementedError

    def set_model_policy(self, org_id: str, policy: ModelPolicy) -> None:
        raise NotImplementedError

    def get_model_policy(self, org_id: str) -> Optional[ModelPolicy]:
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
                    retention_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    name TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    org_id TEXT,
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
            self._ensure_column(conn, "api_keys", "expires_at", "TEXT")
            self._ensure_column(conn, "api_keys", "rotated_at", "TEXT")
            self._ensure_column(conn, "api_keys", "rate_limit_per_minute", "INTEGER")
            self._ensure_column(conn, "api_keys", "ip_allowlist_json", "TEXT")
            self._ensure_column(conn, "orgs", "retention_json", "TEXT")

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
                INSERT INTO orgs (org_id, name, created_at, quotas_json, model_policy_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (org.org_id, org.name, org.created_at, json.dumps({}), json.dumps({})),
            )
        return org

    def get_org(self, org_id: str) -> Optional[Organization]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orgs WHERE org_id = ?", (org_id,)).fetchone()
            if not row:
                return None
            return Organization(org_id=row["org_id"], name=row["name"], created_at=row["created_at"])

    def list_orgs(self) -> List[Organization]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM orgs ORDER BY created_at ASC").fetchall()
            return [
                Organization(org_id=row["org_id"], name=row["name"], created_at=row["created_at"])
                for row in rows
            ]

    def create_user(self, org_id: str, user: User) -> User:
        self.ensure_org(org_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, org_id, name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user.user_id, user.org_id, user.name, user.created_at),
            )
        return user

    def list_users(self, org_id: Optional[str] = None) -> List[User]:
        with self._connect() as conn:
            if org_id is None:
                rows = conn.execute("SELECT * FROM users").fetchall()
            else:
                rows = conn.execute("SELECT * FROM users WHERE org_id = ?", (org_id,)).fetchall()
            return [
                User(user_id=row["user_id"], org_id=row["org_id"], name=row["name"], created_at=row["created_at"])
                for row in rows
            ]

    def create_api_key(self, record: APIKeyRecord) -> APIKeyRecord:
        self.ensure_org(record.org_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO api_keys (key_id, org_id, key, label, role, scopes_json, created_at, active, expires_at, rotated_at, rate_limit_per_minute, ip_allowlist_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.key_id,
                    record.org_id,
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
                    retention_json JSONB
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    name TEXT,
                    created_at TEXT
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    key_id TEXT PRIMARY KEY,
                    org_id TEXT,
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
        self._conn.commit()

    def ensure_org(self, org_id: str, name: Optional[str] = None) -> Organization:
        existing = self.get_org(org_id)
        if existing:
            return existing
        org = Organization(org_id=org_id, name=name or org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orgs (org_id, name, created_at, quotas_json, model_policy_json)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (org.org_id, org.name, org.created_at, json.dumps({}), json.dumps({})),
            )
        self._conn.commit()
        return org

    def get_org(self, org_id: str) -> Optional[Organization]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM orgs WHERE org_id = %s", (org_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Organization(org_id=row[0], name=row[1], created_at=row[2])

    def list_orgs(self) -> List[Organization]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM orgs ORDER BY created_at ASC")
            rows = cur.fetchall()
            return [Organization(org_id=row[0], name=row[1], created_at=row[2]) for row in rows]

    def create_user(self, org_id: str, user: User) -> User:
        self.ensure_org(org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, org_id, name, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (user.user_id, user.org_id, user.name, user.created_at),
            )
        self._conn.commit()
        return user

    def list_users(self, org_id: Optional[str] = None) -> List[User]:
        with self._conn.cursor() as cur:
            if org_id is None:
                cur.execute("SELECT * FROM users")
                rows = cur.fetchall()
            else:
                cur.execute("SELECT * FROM users WHERE org_id = %s", (org_id,))
                rows = cur.fetchall()
            return [User(user_id=row[0], org_id=row[1], name=row[2], created_at=row[3]) for row in rows]

    def create_api_key(self, record: APIKeyRecord) -> APIKeyRecord:
        self.ensure_org(record.org_id)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_keys (key_id, org_id, key, label, role, scopes_json, created_at, active, expires_at, rotated_at, rate_limit_per_minute, ip_allowlist_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.key_id,
                    record.org_id,
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
                        key=row[2],
                        label=row[3],
                        role=row[4] or "developer",
                        scopes=json.loads(row[5] or "[]"),
                        created_at=row[6],
                        active=bool(row[7]),
                        expires_at=row[8],
                        rotated_at=row[9],
                        rate_limit_per_minute=row[10],
                        ip_allowlist=json.loads(row[11] or "[]"),
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
