"""Durable execution queue with backend storage and DLQ."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Awaitable, Callable, Dict, Optional
import sqlite3
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QueueJob:
    job_id: str
    payload: Dict[str, Any]
    attempts: int
    max_attempts: int


class QueueBackend:
    def enqueue(self, payload: Dict[str, Any], max_attempts: int) -> str:
        raise NotImplementedError

    def claim_next(self) -> Optional[QueueJob]:
        raise NotImplementedError

    def mark_done(self, job_id: str) -> None:
        raise NotImplementedError

    def mark_failed(self, job: QueueJob, error: str) -> None:
        raise NotImplementedError

    def requeue(self, job: QueueJob, error: str) -> None:
        raise NotImplementedError


class SQLiteQueueBackend(QueueBackend):
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
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    payload_json TEXT,
                    status TEXT,
                    attempts INTEGER,
                    max_attempts INTEGER,
                    last_error TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dlq (
                    job_id TEXT PRIMARY KEY,
                    payload_json TEXT,
                    error TEXT,
                    attempts INTEGER,
                    created_at TEXT
                )
                """
            )

    def enqueue(self, payload: Dict[str, Any], max_attempts: int) -> str:
        job_id = f"job_{uuid.uuid4().hex}"
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, payload_json, status, attempts, max_attempts, last_error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, json.dumps(payload), "queued", 0, max_attempts, None, now, now),
            )
        return job_id

    def claim_next(self) -> Optional[QueueJob]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, payload_json, attempts, max_attempts
                FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            conn.execute(
                "UPDATE jobs SET status = 'running', updated_at = ? WHERE job_id = ?",
                (_now_iso(), row["job_id"]),
            )
            return QueueJob(
                job_id=row["job_id"],
                payload=json.loads(row["payload_json"] or "{}"),
                attempts=row["attempts"],
                max_attempts=row["max_attempts"],
            )

    def mark_done(self, job_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))

    def mark_failed(self, job: QueueJob, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO dlq (job_id, payload_json, error, attempts, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job.job_id, json.dumps(job.payload), error, job.attempts, _now_iso()),
            )
            conn.execute("DELETE FROM jobs WHERE job_id = ?", (job.job_id,))

    def requeue(self, job: QueueJob, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'queued', attempts = ?, last_error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (job.attempts, error, _now_iso(), job.job_id),
            )


class DurableExecutionQueue:
    def __init__(
        self,
        backend: QueueBackend,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
        poll_interval: float = 0.1,
        max_attempts: int = 3,
    ) -> None:
        self._backend = backend
        self._handler = handler
        self._poll_interval = poll_interval
        self._max_attempts = max_attempts
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._results: Dict[str, asyncio.Future] = {}

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            await asyncio.gather(self._worker_task, return_exceptions=True)

    async def submit(self, payload: Dict[str, Any]) -> Any:
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        job_id = self._backend.enqueue(payload, self._max_attempts)
        self._results[job_id] = future
        return await future

    async def _worker(self) -> None:
        while self._running:
            job = self._backend.claim_next()
            if job is None:
                await asyncio.sleep(self._poll_interval)
                continue
            job.attempts += 1
            try:
                result = await self._handler(job.payload)
                self._backend.mark_done(job.job_id)
                future = self._results.pop(job.job_id, None)
                if future and not future.cancelled():
                    future.set_result(result)
            except Exception as exc:
                error = str(exc)
                if job.attempts >= job.max_attempts:
                    self._backend.mark_failed(job, error)
                    future = self._results.pop(job.job_id, None)
                    if future and not future.cancelled():
                        future.set_exception(exc)
                else:
                    self._backend.requeue(job, error)
                    await asyncio.sleep(self._poll_interval)
