"""Simple async execution queue with worker pool."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional


@dataclass
class QueueJob:
    func: Callable[..., Awaitable[Any]]
    args: tuple
    kwargs: dict
    future: asyncio.Future


class ExecutionQueue:
    def __init__(self, worker_count: int = 2) -> None:
        self._queue: asyncio.Queue[QueueJob] = asyncio.Queue()
        self._workers = [asyncio.create_task(self._worker()) for _ in range(worker_count)]

    async def _worker(self) -> None:
        while True:
            job = await self._queue.get()
            if job.future.cancelled():
                self._queue.task_done()
                continue
            try:
                result = await job.func(*job.args, **job.kwargs)
                if not job.future.cancelled():
                    job.future.set_result(result)
            except Exception as exc:
                if not job.future.cancelled():
                    job.future.set_exception(exc)
            finally:
                self._queue.task_done()

    async def submit(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        await self._queue.put(QueueJob(func=func, args=args, kwargs=kwargs, future=future))
        return await future

    async def shutdown(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
