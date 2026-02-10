"""
SQLite storage backend for runs, sessions, and streaming events.
"""

from __future__ import annotations

import json
import sqlite3
from typing import List, Optional

from datetime import datetime, timezone

from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    SessionMetadata,
    StreamEnvelope,
    RunStatus,
    StreamChannel,
    is_valid_run_transition,
)
from agent_sdk.storage.base import StorageBackend


class SQLiteStorage(StorageBackend):
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
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    user_id TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    tags_json TEXT,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
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
                    tags_json TEXT,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    session_id TEXT,
                    org_id TEXT,
                    stream TEXT,
                    event TEXT,
                    payload_json TEXT,
                    timestamp TEXT,
                    seq INTEGER,
                    status TEXT,
                    metadata_json TEXT
                )
                """
            )
            self._ensure_column(conn, "sessions", "org_id", "TEXT")
            self._ensure_column(conn, "runs", "org_id", "TEXT")
            self._ensure_column(conn, "events", "org_id", "TEXT")

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column in existing:
            return
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")

    def create_session(self, session: SessionMetadata) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, org_id, user_id, created_at, updated_at, tags_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
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

    def update_session(self, session: SessionMetadata) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions SET
                    org_id = ?,
                    user_id = ?,
                    created_at = ?,
                    updated_at = ?,
                    tags_json = ?,
                    metadata_json = ?
                WHERE session_id = ?
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

    def get_session(self, session_id: str) -> Optional[SessionMetadata]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            return SessionMetadata(
                session_id=row["session_id"],
                org_id=row["org_id"] or "default",
                user_id=row["user_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                tags=json.loads(row["tags_json"] or "{}"),
                metadata=json.loads(row["metadata_json"] or "{}"),
            )

    def list_sessions(self, limit: int = 100) -> List[SessionMetadata]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            sessions = []
            for row in rows:
                sessions.append(
                    SessionMetadata(
                        session_id=row["session_id"],
                        org_id=row["org_id"] or "default",
                        user_id=row["user_id"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        tags=json.loads(row["tags_json"] or "{}"),
                        metadata=json.loads(row["metadata_json"] or "{}"),
                    )
                )
            return sessions

    def create_run(self, run: RunMetadata) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, session_id, agent_id, org_id, status, model, created_at,
                    started_at, ended_at, tags_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def update_run(self, run: RunMetadata) -> None:
        with self._connect() as conn:
            current = conn.execute(
                "SELECT status FROM runs WHERE run_id = ?",
                (run.run_id,),
            ).fetchone()
            if current:
                current_status = RunStatus(current["status"])
                if not is_valid_run_transition(current_status, run.status):
                    raise ValueError(
                        f"Invalid run status transition: {current_status.value} -> {run.status.value}"
                    )
            conn.execute(
                """
                UPDATE runs SET
                    session_id = ?,
                    agent_id = ?,
                    org_id = ?,
                    status = ?,
                    model = ?,
                    created_at = ?,
                    started_at = ?,
                    ended_at = ?,
                    tags_json = ?,
                    metadata_json = ?
                WHERE run_id = ?
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

    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if not row:
                return None
            return RunMetadata(
                run_id=row["run_id"],
                session_id=row["session_id"],
                agent_id=row["agent_id"],
                org_id=row["org_id"] or "default",
                status=RunStatus(row["status"]),
                model=row["model"],
                created_at=row["created_at"],
                started_at=row["started_at"],
                ended_at=row["ended_at"],
                tags=json.loads(row["tags_json"] or "{}"),
                metadata=json.loads(row["metadata_json"] or "{}"),
            )

    def append_event(self, event: StreamEnvelope) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    run_id, session_id, org_id, stream, event, payload_json,
                    timestamp, seq, status, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def list_events(self, run_id: str, limit: int = 1000) -> List[StreamEnvelope]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE run_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (run_id, limit),
            ).fetchall()
            events = []
            for row in rows:
                events.append(
                    StreamEnvelope(
                        run_id=row["run_id"],
                        session_id=row["session_id"],
                        stream=StreamChannel(row["stream"]),
                        event=row["event"],
                        payload=json.loads(row["payload_json"] or "{}"),
                        timestamp=row["timestamp"],
                        seq=row["seq"],
                        status=row["status"],
                        metadata=json.loads(row["metadata_json"] or "{}"),
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
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                WHERE run_id = ? AND (seq IS NULL OR seq >= ?)
                ORDER BY id ASC
                LIMIT ?
                """,
                (run_id, from_seq, limit),
            ).fetchall()
            events = []
            for row in rows:
                events.append(
                    StreamEnvelope(
                        run_id=row["run_id"],
                        session_id=row["session_id"],
                        stream=StreamChannel(row["stream"]),
                        event=row["event"],
                        payload=json.loads(row["payload_json"] or "{}"),
                        timestamp=row["timestamp"],
                        seq=row["seq"],
                        status=row["status"],
                        metadata=json.loads(row["metadata_json"] or "{}"),
                    )
                )
            return events

    def delete_events(self, run_id: str, before_seq: Optional[int] = None) -> int:
        with self._connect() as conn:
            if before_seq is None:
                cur = conn.execute("DELETE FROM events WHERE run_id = ?", (run_id,))
                return cur.rowcount
            cur = conn.execute(
                """
                DELETE FROM events
                WHERE run_id = ? AND seq IS NOT NULL AND seq < ?
                """,
                (run_id, before_seq),
            )
            return cur.rowcount

    def recover_in_flight_runs(self) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT run_id, session_id, agent_id, org_id, model, created_at, started_at,
                       tags_json, metadata_json
                FROM runs
                WHERE status IN (?, ?)
                """,
                (RunStatus.RUNNING.value, RunStatus.ACCEPTED.value),
            ).fetchall()
            count = 0
            for row in rows:
                metadata = json.loads(row["metadata_json"] or "{}")
                metadata.update({"recovered": True, "recovered_at": now})
                conn.execute(
                    """
                    UPDATE runs SET status = ?, ended_at = ?, metadata_json = ?
                    WHERE run_id = ?
                    """,
                    (RunStatus.ERROR.value, now, json.dumps(metadata), row["run_id"]),
                )
                seq_row = conn.execute(
                    "SELECT MAX(seq) AS max_seq FROM events WHERE run_id = ?",
                    (row["run_id"],),
                ).fetchone()
                max_seq = seq_row["max_seq"] if seq_row else None
                next_seq = 0 if max_seq is None else max_seq + 1
                conn.execute(
                    """
                    INSERT INTO events (
                        run_id, session_id, org_id, stream, event, payload_json,
                        timestamp, seq, status, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["run_id"],
                        row["session_id"],
                        row["org_id"] or "default",
                        StreamChannel.LIFECYCLE.value,
                        "recovered",
                        json.dumps({"reason": "server_restart"}),
                        now,
                        next_seq,
                        RunStatus.ERROR.value,
                        json.dumps({"org_id": row["org_id"] or "default", "recovery": True}),
                    ),
                )
                count += 1
            return count

    def delete_run(self, run_id: str) -> int:
        with self._connect() as conn:
            conn.execute("DELETE FROM events WHERE run_id = ?", (run_id,))
            cur = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            return cur.rowcount

    def delete_session(self, session_id: str) -> int:
        with self._connect() as conn:
            conn.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM runs WHERE session_id = ?", (session_id,))
            cur = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return cur.rowcount
