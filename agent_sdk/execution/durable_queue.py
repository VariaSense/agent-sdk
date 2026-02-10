"""Durable execution queue with backend storage and DLQ."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Awaitable, Callable, Dict, Optional
import sqlite3
import uuid

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional
    redis = None

try:
    import boto3  # type: ignore
except Exception:  # pragma: no cover - optional
    boto3 = None

try:
    from kafka import KafkaProducer, KafkaConsumer  # type: ignore
except Exception:  # pragma: no cover - optional
    KafkaProducer = None
    KafkaConsumer = None


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


class RedisQueueBackend(QueueBackend):
    def __init__(self, url: str, queue_key: str = "agent_sdk:queue", dlq_key: str = "agent_sdk:dlq", client=None):
        if redis is None and client is None:
            raise RuntimeError("redis is required for RedisQueueBackend")
        self._queue_key = queue_key
        self._dlq_key = dlq_key
        self._client = client or redis.Redis.from_url(url)

    def _job_key(self, job_id: str) -> str:
        return f"agent_sdk:job:{job_id}"

    def enqueue(self, payload: Dict[str, Any], max_attempts: int) -> str:
        job_id = f"job_{uuid.uuid4().hex}"
        job_key = self._job_key(job_id)
        self._client.hset(
            job_key,
            mapping={
                "payload_json": json.dumps(payload),
                "attempts": 0,
                "max_attempts": max_attempts,
            },
        )
        self._client.lpush(self._queue_key, job_id)
        return job_id

    def claim_next(self) -> Optional[QueueJob]:
        job_id = self._client.rpop(self._queue_key)
        if job_id is None:
            return None
        if isinstance(job_id, bytes):
            job_id = job_id.decode("utf-8")
        job_key = self._job_key(job_id)
        payload_json = self._client.hget(job_key, "payload_json") or b"{}"
        attempts = int(self._client.hget(job_key, "attempts") or 0)
        max_attempts = int(self._client.hget(job_key, "max_attempts") or 0)
        return QueueJob(
            job_id=job_id,
            payload=json.loads(payload_json),
            attempts=attempts,
            max_attempts=max_attempts,
        )

    def mark_done(self, job_id: str) -> None:
        self._client.delete(self._job_key(job_id))

    def mark_failed(self, job: QueueJob, error: str) -> None:
        self._client.hset(
            self._job_key(job.job_id),
            mapping={"error": error, "attempts": job.attempts},
        )
        self._client.lpush(self._dlq_key, job.job_id)

    def requeue(self, job: QueueJob, error: str) -> None:
        self._client.hset(
            self._job_key(job.job_id),
            mapping={"attempts": job.attempts, "last_error": error},
        )
        self._client.lpush(self._queue_key, job.job_id)


class SQSQueueBackend(QueueBackend):
    def __init__(self, queue_url: str, dlq_url: Optional[str] = None, client=None):
        if boto3 is None and client is None:
            raise RuntimeError("boto3 is required for SQSQueueBackend")
        self._client = client or boto3.client("sqs")
        self._queue_url = queue_url
        self._dlq_url = dlq_url
        self._inflight: Dict[str, str] = {}

    def enqueue(self, payload: Dict[str, Any], max_attempts: int) -> str:
        body = json.dumps({"payload": payload, "attempts": 0, "max_attempts": max_attempts})
        response = self._client.send_message(QueueUrl=self._queue_url, MessageBody=body)
        return response.get("MessageId", f"job_{uuid.uuid4().hex}")

    def claim_next(self) -> Optional[QueueJob]:
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=0,
        )
        messages = response.get("Messages", [])
        if not messages:
            return None
        message = messages[0]
        data = json.loads(message.get("Body", "{}"))
        job_id = message.get("MessageId", f"job_{uuid.uuid4().hex}")
        self._inflight[job_id] = message.get("ReceiptHandle")
        return QueueJob(
            job_id=job_id,
            payload=data.get("payload", {}),
            attempts=int(data.get("attempts", 0)),
            max_attempts=int(data.get("max_attempts", 1)),
        )

    def mark_done(self, job_id: str) -> None:
        receipt = self._inflight.pop(job_id, None)
        if receipt:
            self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt)

    def mark_failed(self, job: QueueJob, error: str) -> None:
        receipt = self._inflight.pop(job.job_id, None)
        if receipt:
            self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt)
        if self._dlq_url:
            body = json.dumps(
                {
                    "payload": job.payload,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "error": error,
                }
            )
            self._client.send_message(QueueUrl=self._dlq_url, MessageBody=body)

    def requeue(self, job: QueueJob, error: str) -> None:
        receipt = self._inflight.pop(job.job_id, None)
        if receipt:
            self._client.delete_message(QueueUrl=self._queue_url, ReceiptHandle=receipt)
        body = json.dumps(
            {
                "payload": job.payload,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
                "last_error": error,
            }
        )
        self._client.send_message(QueueUrl=self._queue_url, MessageBody=body)


class KafkaQueueBackend(QueueBackend):
    def __init__(self, topic: str, client=None, group_id: str = "agent-sdk"):
        if (KafkaProducer is None or KafkaConsumer is None) and client is None:
            raise RuntimeError("kafka-python is required for KafkaQueueBackend")
        self._topic = topic
        self._producer = client.get("producer") if isinstance(client, dict) else None
        self._consumer = client.get("consumer") if isinstance(client, dict) else None
        if self._producer is None:
            self._producer = KafkaProducer()
        if self._consumer is None:
            self._consumer = KafkaConsumer(topic, group_id=group_id, auto_offset_reset="earliest")
        self._inflight: Dict[str, Any] = {}

    def enqueue(self, payload: Dict[str, Any], max_attempts: int) -> str:
        job_id = f"job_{uuid.uuid4().hex}"
        body = json.dumps({"job_id": job_id, "payload": payload, "attempts": 0, "max_attempts": max_attempts})
        self._producer.send(self._topic, value=body.encode("utf-8"))
        return job_id

    def claim_next(self) -> Optional[QueueJob]:
        records = self._consumer.poll(timeout_ms=0)
        for _, messages in records.items():
            if not messages:
                continue
            message = messages[0]
            data = json.loads(message.value.decode("utf-8"))
            job_id = data.get("job_id", f"job_{uuid.uuid4().hex}")
            self._inflight[job_id] = message
            return QueueJob(
                job_id=job_id,
                payload=data.get("payload", {}),
                attempts=int(data.get("attempts", 0)),
                max_attempts=int(data.get("max_attempts", 1)),
            )
        return None

    def mark_done(self, job_id: str) -> None:
        self._inflight.pop(job_id, None)

    def mark_failed(self, job: QueueJob, error: str) -> None:
        self._inflight.pop(job.job_id, None)

    def requeue(self, job: QueueJob, error: str) -> None:
        body = json.dumps(
            {
                "job_id": job.job_id,
                "payload": job.payload,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
                "last_error": error,
            }
        )
        self._producer.send(self._topic, value=body.encode("utf-8"))


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
