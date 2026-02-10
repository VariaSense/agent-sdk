"""In-memory scheduler for cron-based runs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Protocol
import secrets

from croniter import croniter


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class ScheduleEntry:
    schedule_id: str
    org_id: str
    task: str
    cron: str
    enabled: bool = True
    next_run_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: _now().isoformat())


class SchedulerStore(Protocol):
    def load(self) -> List[ScheduleEntry]:
        ...

    def save(self, entry: ScheduleEntry) -> None:
        ...

    def delete(self, schedule_id: str) -> None:
        ...


class SQLiteSchedulerStore:
    def __init__(self, path: str):
        import sqlite3

        self._path = path
        self._sqlite3 = sqlite3
        self._init_db()

    def _connect(self):
        conn = self._sqlite3.connect(self._path)
        conn.row_factory = self._sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    schedule_id TEXT PRIMARY KEY,
                    org_id TEXT,
                    task TEXT,
                    cron TEXT,
                    enabled INTEGER,
                    next_run_at TEXT,
                    created_at TEXT
                )
                """
            )

    def load(self) -> List[ScheduleEntry]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM schedules").fetchall()
            return [
                ScheduleEntry(
                    schedule_id=row["schedule_id"],
                    org_id=row["org_id"],
                    task=row["task"],
                    cron=row["cron"],
                    enabled=bool(row["enabled"]),
                    next_run_at=row["next_run_at"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def save(self, entry: ScheduleEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO schedules (
                    schedule_id, org_id, task, cron, enabled, next_run_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.schedule_id,
                    entry.org_id,
                    entry.task,
                    entry.cron,
                    1 if entry.enabled else 0,
                    entry.next_run_at,
                    entry.created_at,
                ),
            )

    def delete(self, schedule_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM schedules WHERE schedule_id = ?", (schedule_id,))


class Scheduler:
    def __init__(
        self,
        submitter: Callable[[ScheduleEntry], asyncio.Future],
        poll_interval: float = 1.0,
        store: Optional[SchedulerStore] = None,
    ):
        self._submitter = submitter
        self._poll_interval = poll_interval
        self._schedules: Dict[str, ScheduleEntry] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._store = store
        if self._store:
            for entry in self._store.load():
                self._schedules[entry.schedule_id] = entry

    def add_schedule(self, org_id: str, task: str, cron: str, enabled: bool = True) -> ScheduleEntry:
        schedule_id = f"sch_{secrets.token_hex(6)}"
        entry = ScheduleEntry(
            schedule_id=schedule_id,
            org_id=org_id,
            task=task,
            cron=cron,
            enabled=enabled,
        )
        entry.next_run_at = self._next_run(entry)
        self._schedules[entry.schedule_id] = entry
        if self._store:
            self._store.save(entry)
        return entry

    def list_schedules(self, org_id: Optional[str] = None) -> List[ScheduleEntry]:
        if org_id is None:
            return list(self._schedules.values())
        return [entry for entry in self._schedules.values() if entry.org_id == org_id]

    def remove_schedule(self, schedule_id: str) -> bool:
        removed = self._schedules.pop(schedule_id, None) is not None
        if removed and self._store:
            self._store.delete(schedule_id)
        return removed

    def _next_run(self, entry: ScheduleEntry) -> Optional[str]:
        if not entry.enabled:
            return None
        iterator = croniter(entry.cron, _now())
        return iterator.get_next(datetime).isoformat()

    async def start(self) -> None:
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_loop(self) -> None:
        while self._running:
            now = _now()
            due = [entry for entry in self._schedules.values() if entry.enabled and entry.next_run_at]
            for entry in due:
                next_run = datetime.fromisoformat(entry.next_run_at)
                if next_run <= now:
                    await self._submitter(entry)
                    entry.next_run_at = self._next_run(entry)
                    if self._store:
                        self._store.save(entry)
            await asyncio.sleep(self._poll_interval)
