"""Tests for durable execution queue."""

import os
import tempfile
import asyncio

from agent_sdk.execution.durable_queue import DurableExecutionQueue, SQLiteQueueBackend


async def _handler(payload):
    await asyncio.sleep(0.01)
    return payload["value"] + 1


def test_durable_queue_executes_job():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "queue.db")
            queue = DurableExecutionQueue(
                backend=SQLiteQueueBackend(path),
                handler=_handler,
                poll_interval=0.01,
                max_attempts=2,
            )
            await queue.start()
            result = await queue.submit({"value": 1})
            await queue.stop()
            return result

    result = asyncio.run(_run())
    assert result == 2


def test_durable_queue_moves_to_dlq_on_failure():
    async def _handler_fail(payload):
        raise RuntimeError("boom")

    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "queue.db")
            backend = SQLiteQueueBackend(path)
            queue = DurableExecutionQueue(
                backend=backend,
                handler=_handler_fail,
                poll_interval=0.01,
                max_attempts=1,
            )
            await queue.start()
            try:
                await queue.submit({"value": 1})
            except RuntimeError:
                pass
            await queue.stop()
            with backend._connect() as conn:
                rows = conn.execute("SELECT * FROM dlq").fetchall()
                return len(rows)

    dlq_count = asyncio.run(_run())
    assert dlq_count == 1
