"""
In-memory run event store with backpressure support.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

from agent_sdk.observability.stream_envelope import StreamEnvelope, StreamChannel


@dataclass
class RunBuffer:
    history: Deque[StreamEnvelope]
    queue: asyncio.Queue
    max_events: int


class RunEventStore:
    def __init__(self, max_events: int = 1000, queue_size: int = 200):
        self._runs: Dict[str, RunBuffer] = {}
        self._max_events = max_events
        self._queue_size = queue_size

    def create_run(self, run_id: str) -> None:
        if run_id in self._runs:
            return
        self._runs[run_id] = RunBuffer(
            history=deque(maxlen=self._max_events),
            queue=asyncio.Queue(maxsize=self._queue_size),
            max_events=self._max_events,
        )

    def has_run(self, run_id: str) -> bool:
        return run_id in self._runs

    def append_event(self, run_id: str, event: StreamEnvelope) -> None:
        if run_id not in self._runs:
            self.create_run(run_id)
        buffer = self._runs[run_id]
        buffer.history.append(event)
        try:
            buffer.queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                buffer.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            buffer.queue.put_nowait(event)

    def list_events(self, run_id: str) -> List[StreamEnvelope]:
        if run_id not in self._runs:
            return []
        return list(self._runs[run_id].history)

    async def stream(self, run_id: str):
        if run_id not in self._runs:
            return
        buffer = self._runs[run_id]
        for event in list(buffer.history):
            yield event
        while True:
            event = await buffer.queue.get()
            yield event
            if event.stream == StreamChannel.LIFECYCLE and event.event in {"end", "error", "timeout", "canceled"}:
                break
