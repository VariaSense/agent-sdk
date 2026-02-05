"""
SQLite storage backend for runs, sessions, and streaming events.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import List, Optional

from agent_sdk.observability.stream_envelope import RunMetadata, SessionMetadata, StreamEnvelope, RunStatus, StreamChannel
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

    def create_session(self, session: SessionMetadata) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, user_id, created_at, updated_at, tags_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
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
                    user_id = ?,
                    created_at = ?,
                    updated_at = ?,
                    tags_json = ?,
                    metadata_json = ?
                WHERE session_id = ?
                """,
                (
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
                    run_id, session_id, agent_id, status, model, created_at,
                    started_at, ended_at, tags_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.session_id,
                    run.agent_id,
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
            conn.execute(
                """
                UPDATE runs SET
                    session_id = ?,
                    agent_id = ?,
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
                    run_id, session_id, stream, event, payload_json,
                    timestamp, seq, status, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.session_id,
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
