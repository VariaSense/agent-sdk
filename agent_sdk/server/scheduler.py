"""In-memory scheduler for cron-based runs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional
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


class Scheduler:
    def __init__(self, submitter: Callable[[ScheduleEntry], asyncio.Future], poll_interval: float = 1.0):
        self._submitter = submitter
        self._poll_interval = poll_interval
        self._schedules: Dict[str, ScheduleEntry] = {}
        self._task: Optional[asyncio.Task] = None
        self._running = False

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
        return entry

    def list_schedules(self, org_id: Optional[str] = None) -> List[ScheduleEntry]:
        if org_id is None:
            return list(self._schedules.values())
        return [entry for entry in self._schedules.values() if entry.org_id == org_id]

    def remove_schedule(self, schedule_id: str) -> bool:
        return self._schedules.pop(schedule_id, None) is not None

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
            await asyncio.sleep(self._poll_interval)
