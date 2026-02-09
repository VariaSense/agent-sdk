"""Tests for execution queue worker pool."""

import asyncio

from agent_sdk.execution.queue import ExecutionQueue


async def _echo(value: int) -> int:
    await asyncio.sleep(0.01)
    return value + 1


def test_execution_queue_runs_tasks():
    async def _run():
        queue = ExecutionQueue(worker_count=1)
        result = await queue.submit(_echo, 1)
        await queue.shutdown()
        return result

    result = asyncio.run(_run())
    assert result == 2
