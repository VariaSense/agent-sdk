"""Postgres storage backend for runs, sessions, and streaming events."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional, Callable

from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    SessionMetadata,
    StreamEnvelope,
    RunStatus,
    StreamChannel,
    is_valid_run_transition,
)
from agent_sdk.storage.base import StorageBackend
from agent_sdk.encryption import maybe_encrypt, maybe_decrypt

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None


class PostgresStorage(StorageBackend):
    def __init__(
        self,
        dsn: str,
        initialize_schema: bool = True,
        encryption_resolver: Optional[Callable[[str], Optional[str]]] = None,
    ):
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgresStorage")
        self.dsn = dsn
        self._conn = psycopg.connect(dsn)
        self._encryption_resolver = encryption_resolver
        if initialize_schema:
            self._init_db()

    def set_encryption_resolver(self, resolver: Optional[Callable[[str], Optional[str]]]) -> None:
        self._encryption_resolver = resolver

    def _key_for_org(self, org_id: Optional[str]) -> Optional[str]:
        if not self._encryption_resolver:
            return None
        return self._encryption_resolver(org_id or "default")

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
        key = self._key_for_org(session.org_id)
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
                    json.dumps(maybe_encrypt(session.tags, key)),
                    json.dumps(maybe_encrypt(session.metadata, key)),
                ),
            )
        self._conn.commit()

    def update_session(self, session: SessionMetadata) -> None:
        key = self._key_for_org(session.org_id)
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
                    json.dumps(maybe_encrypt(session.tags, key)),
                    json.dumps(maybe_encrypt(session.metadata, key)),
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
            key = self._key_for_org(row[1] or "default")
            return SessionMetadata(
                session_id=row[0],
                org_id=row[1] or "default",
                user_id=row[2],
                created_at=row[3],
                updated_at=row[4],
                tags=maybe_decrypt(json.loads(row[5] or "{}"), key),
                metadata=maybe_decrypt(json.loads(row[6] or "{}"), key),
            )

    def list_sessions(self, limit: int = 100) -> List[SessionMetadata]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
            sessions = []
            for row in rows:
                key = self._key_for_org(row[1] or "default")
                sessions.append(
                    SessionMetadata(
                        session_id=row[0],
                        org_id=row[1] or "default",
                        user_id=row[2],
                        created_at=row[3],
                        updated_at=row[4],
                        tags=maybe_decrypt(json.loads(row[5] or "{}"), key),
                        metadata=maybe_decrypt(json.loads(row[6] or "{}"), key),
                    )
                )
            return sessions

    def create_run(self, run: RunMetadata) -> None:
        key = self._key_for_org(run.org_id)
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
                    json.dumps(maybe_encrypt(run.tags, key)),
                    json.dumps(maybe_encrypt(run.metadata, key)),
                ),
            )
        self._conn.commit()

    def update_run(self, run: RunMetadata) -> None:
        key = self._key_for_org(run.org_id)
        with self._conn.cursor() as cur:
            cur.execute("SELECT status FROM runs WHERE run_id = %s", (run.run_id,))
            row = cur.fetchone()
            if row:
                current_status = RunStatus(row[0])
                if not is_valid_run_transition(current_status, run.status):
                    raise ValueError(
                        f"Invalid run status transition: {current_status.value} -> {run.status.value}"
                    )
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
                    json.dumps(maybe_encrypt(run.tags, key)),
                    json.dumps(maybe_encrypt(run.metadata, key)),
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
            key = self._key_for_org(row[3] or "default")
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
                tags=maybe_decrypt(json.loads(row[9] or "{}"), key),
                metadata=maybe_decrypt(json.loads(row[10] or "{}"), key),
            )

    def list_runs(self, org_id: Optional[str] = None, limit: int = 1000) -> List[RunMetadata]:
        with self._conn.cursor() as cur:
            if org_id:
                cur.execute(
                    """
                    SELECT * FROM runs
                    WHERE org_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM runs
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            rows = cur.fetchall()
            runs = []
            for row in rows:
                key = self._key_for_org(row[3] or "default")
                runs.append(
                    RunMetadata(
                        run_id=row[0],
                        session_id=row[1],
                        agent_id=row[2],
                        org_id=row[3] or "default",
                        status=RunStatus(row[4]),
                        model=row[5],
                        created_at=row[6],
                        started_at=row[7],
                        ended_at=row[8],
                        tags=maybe_decrypt(json.loads(row[9] or "{}"), key),
                        metadata=maybe_decrypt(json.loads(row[10] or "{}"), key),
                    )
                )
            return runs

    def append_event(self, event: StreamEnvelope) -> None:
        key = self._key_for_org(event.metadata.get("org_id", "default"))
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
                    json.dumps(maybe_encrypt(event.payload, key)),
                    event.timestamp,
                    event.seq,
                    event.status,
                    json.dumps(maybe_encrypt(event.metadata, key)),
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
            events = []
            for row in rows:
                key = self._key_for_org(row[2] or "default")
                events.append(
                    StreamEnvelope(
                        run_id=row[0],
                        session_id=row[1],
                        stream=StreamChannel(row[3]),
                        event=row[4],
                        payload=maybe_decrypt(json.loads(row[5] or "{}"), key),
                        timestamp=row[6],
                        seq=row[7],
                        status=row[8],
                        metadata=maybe_decrypt(json.loads(row[9] or "{}"), key),
                    )
                )
            return events

    def list_events_from(
        self,
        run_id: str,
        from_seq: Optional[int] = None,
        limit: int = 1000,
    ) -> List[StreamEnvelope]:
        if from_seq is None:
            return self.list_events(run_id, limit=limit)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, session_id, org_id, stream, event, payload_json, timestamp, seq, status, metadata_json
                FROM events WHERE run_id = %s AND (seq IS NULL OR seq >= %s)
                ORDER BY id ASC LIMIT %s
                """,
                (run_id, from_seq, limit),
            )
            rows = cur.fetchall()
            events = []
            for row in rows:
                key = self._key_for_org(row[2] or "default")
                events.append(
                    StreamEnvelope(
                        run_id=row[0],
                        session_id=row[1],
                        stream=StreamChannel(row[3]),
                        event=row[4],
                        payload=maybe_decrypt(json.loads(row[5] or "{}"), key),
                        timestamp=row[6],
                        seq=row[7],
                        status=row[8],
                        metadata=maybe_decrypt(json.loads(row[9] or "{}"), key),
                    )
                )
            return events

    def delete_events(self, run_id: str, before_seq: Optional[int] = None) -> int:
        with self._conn.cursor() as cur:
            if before_seq is None:
                cur.execute("DELETE FROM events WHERE run_id = %s", (run_id,))
            else:
                cur.execute(
                    """
                    DELETE FROM events
                    WHERE run_id = %s AND seq IS NOT NULL AND seq < %s
                    """,
                    (run_id, before_seq),
                )
            deleted = cur.rowcount
        self._conn.commit()
        return deleted

    def recover_in_flight_runs(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, session_id, agent_id, org_id, model, created_at, started_at,
                       tags_json, metadata_json
                FROM runs
                WHERE status IN (%s, %s)
                """,
                (RunStatus.RUNNING.value, RunStatus.ACCEPTED.value),
            )
            rows = cur.fetchall()
            count = 0
            for row in rows:
                run_id = row[0]
                session_id = row[1]
                org_id = row[3] or "default"
                metadata = json.loads(row[8] or "{}")
                metadata.update({"recovered": True, "recovered_at": now})
                cur.execute(
                    "UPDATE runs SET status = %s, ended_at = %s, metadata_json = %s WHERE run_id = %s",
                    (RunStatus.ERROR.value, now, json.dumps(metadata), run_id),
                )
                cur.execute("SELECT MAX(seq) FROM events WHERE run_id = %s", (run_id,))
                max_seq_row = cur.fetchone()
                max_seq = max_seq_row[0] if max_seq_row else None
                next_seq = 0 if max_seq is None else max_seq + 1
                cur.execute(
                    """
                    INSERT INTO events (
                        run_id, session_id, org_id, stream, event, payload_json,
                        timestamp, seq, status, metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id,
                        session_id,
                        org_id,
                        StreamChannel.LIFECYCLE.value,
                        "recovered",
                        json.dumps({"reason": "server_restart"}),
                        now,
                        next_seq,
                        RunStatus.ERROR.value,
                        json.dumps({"org_id": org_id, "recovery": True}),
                    ),
                )
                count += 1
            self._conn.commit()
            return count

    def prune_runs(self, org_id: str, before_timestamp: str) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT run_id FROM runs WHERE org_id = %s AND created_at < %s",
                (org_id, before_timestamp),
            )
            rows = cur.fetchall()
            count = 0
            for row in rows:
                count += self.delete_run(row[0])
            return count

    def prune_sessions(self, org_id: str, before_timestamp: str) -> int:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT session_id FROM sessions WHERE org_id = %s AND created_at < %s",
                (org_id, before_timestamp),
            )
            rows = cur.fetchall()
            count = 0
            for row in rows:
                count += self.delete_session(row[0])
            return count

    def delete_run(self, run_id: str) -> int:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE run_id = %s", (run_id,))
            cur.execute("DELETE FROM runs WHERE run_id = %s", (run_id,))
            deleted = cur.rowcount
        self._conn.commit()
        return deleted

    def delete_session(self, session_id: str) -> int:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM events WHERE session_id = %s", (session_id,))
            cur.execute("DELETE FROM runs WHERE session_id = %s", (session_id,))
            cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            deleted = cur.rowcount
        self._conn.commit()
        return deleted
