"""Tests for scheduler persistence."""

import asyncio

from agent_sdk.server.scheduler import Scheduler, SQLiteSchedulerStore


def test_scheduler_persists_entries(tmp_path):
    db_path = tmp_path / "sched.db"
    store = SQLiteSchedulerStore(str(db_path))

    async def _submit(_entry):
        return None

    scheduler = Scheduler(_submit, store=store)
    entry = scheduler.add_schedule("default", "ping", "*/5 * * * *")
    scheduler_loaded = Scheduler(_submit, store=store)
    entries = scheduler_loaded.list_schedules()
    assert any(item.schedule_id == entry.schedule_id for item in entries)
