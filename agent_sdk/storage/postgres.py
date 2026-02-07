"""Postgres storage backend for runs, sessions, and streaming events."""

from __future__ import annotations

import json
from typing import List, Optional

from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    SessionMetadata,
    StreamEnvelope,
    RunStatus,
    StreamChannel,
)
from agent_sdk.storage.base import StorageBackend

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None


class PostgresStorage(StorageBackend):
    def __init__(self, dsn: str, initialize_schema: bool = True):
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgresStorage")
        self.dsn = dsn
        self._conn = psycopg.connect(dsn)
        if initialize_schema:
            self._init_db()

    def _init_db(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    user_id TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    tags_json JSONB,
                    metadata_json JSONB
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    agent_id TEXT,
                    org_id TEXT,
                    status TEXT,
                    model TEXT,
                    created_at TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    tags_json JSONB,
                    metadata_json JSONB
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    run_id TEXT,
                    session_id TEXT,
                    org_id TEXT,
                    stream TEXT,
                    event TEXT,
                    payload_json JSONB,
                    timestamp TEXT,
                    seq INTEGER,
                    status TEXT,
                    metadata_json JSONB
                );
                """
            )
        self._conn.commit()

    def create_session(self, session: SessionMetadata) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (
                    session_id, org_id, user_id, created_at, updated_at, tags_json, metadata_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session.session_id,
                    session.org_id,
                    session.user_id,
                    session.created_at,
                    session.updated_at,
                    json.dumps(session.tags),
                    json.dumps(session.metadata),
                ),
            )
        self._conn.commit()

    def update_session(self, session: SessionMetadata) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sessions SET
                    org_id = %s,
                    user_id = %s,
                    created_at = %s,
                    updated_at = %s,
                    tags_json = %s,
                    metadata_json = %s
                WHERE session_id = %s
                """,
                (
                    session.org_id,
                    session.user_id,
                    session.created_at,
                    session.updated_at,
                    json.dumps(session.tags),
                    json.dumps(session.metadata),
                    session.session_id,
                ),
            )
        self._conn.commit()

    def get_session(self, session_id: str) -> Optional[SessionMetadata]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM sessions WHERE session_id = %s", (session_id,))
            row = cur.fetchone()
            if not row:
                return None
            return SessionMetadata(
                session_id=row[0],
                org_id=row[1] or "default",
                user_id=row[2],
                created_at=row[3],
                updated_at=row[4],
                tags=json.loads(row[5] or "{}"),
                metadata=json.loads(row[6] or "{}"),
            )

    def list_sessions(self, limit: int = 100) -> List[SessionMetadata]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
            return [
                SessionMetadata(
                    session_id=row[0],
                    org_id=row[1] or "default",
                    user_id=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                    tags=json.loads(row[5] or "{}"),
                    metadata=json.loads(row[6] or "{}"),
                )
                for row in rows
            ]

    def create_run(self, run: RunMetadata) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO runs (
                    run_id, session_id, agent_id, org_id, status, model, created_at,
                    started_at, ended_at, tags_json, metadata_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run.run_id,
                    run.session_id,
                    run.agent_id,
                    run.org_id,
                    run.status.value,
                    run.model,
                    run.created_at,
                    run.started_at,
                    run.ended_at,
                    json.dumps(run.tags),
                    json.dumps(run.metadata),
                ),
            )
        self._conn.commit()

    def update_run(self, run: RunMetadata) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE runs SET
                    session_id = %s,
                    agent_id = %s,
                    org_id = %s,
                    status = %s,
                    model = %s,
                    created_at = %s,
                    started_at = %s,
                    ended_at = %s,
                    tags_json = %s,
                    metadata_json = %s
                WHERE run_id = %s
                """,
                (
                    run.session_id,
                    run.agent_id,
                    run.org_id,
                    run.status.value,
                    run.model,
                    run.created_at,
                    run.started_at,
                    run.ended_at,
                    json.dumps(run.tags),
                    json.dumps(run.metadata),
                    run.run_id,
                ),
            )
        self._conn.commit()

    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT * FROM runs WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            return RunMetadata(
                run_id=row[0],
                session_id=row[1],
                agent_id=row[2],
                org_id=row[3] or "default",
                status=RunStatus(row[4]),
                model=row[5],
                created_at=row[6],
                started_at=row[7],
                ended_at=row[8],
                tags=json.loads(row[9] or "{}"),
                metadata=json.loads(row[10] or "{}"),
            )

    def append_event(self, event: StreamEnvelope) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (
                    run_id, session_id, org_id, stream, event, payload_json,
                    timestamp, seq, status, metadata_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    event.run_id,
                    event.session_id,
                    event.metadata.get("org_id", "default"),
                    event.stream.value,
                    event.event,
                    json.dumps(event.payload),
                    event.timestamp,
                    event.seq,
                    event.status,
                    json.dumps(event.metadata),
                ),
            )
        self._conn.commit()

    def list_events(self, run_id: str, limit: int = 1000) -> List[StreamEnvelope]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, session_id, org_id, stream, event, payload_json, timestamp, seq, status, metadata_json
                FROM events WHERE run_id = %s ORDER BY id ASC LIMIT %s
                """,
                (run_id, limit),
            )
            rows = cur.fetchall()
            return [
                StreamEnvelope(
                    run_id=row[0],
                    session_id=row[1],
                    stream=StreamChannel(row[3]),
                    event=row[4],
                    payload=json.loads(row[5] or "{}"),
                    timestamp=row[6],
                    seq=row[7],
                    status=row[8],
                    metadata=json.loads(row[9] or "{}"),
                )
                for row in rows
            ]
