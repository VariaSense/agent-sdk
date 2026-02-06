"""
In-memory run event store with backpressure support.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional

from agent_sdk.observability.stream_envelope import StreamEnvelope, StreamChannel
from agent_sdk.observability.run_logs import RunLogExporter


@dataclass
class RunBuffer:
    history: Deque[StreamEnvelope]
    queue: asyncio.Queue
    max_events: int


class RunEventStore:
    def __init__(
        self,
        max_events: int = 1000,
        queue_size: int = 200,
        exporters: Optional[List[RunLogExporter]] = None,
    ):
        self._runs: Dict[str, RunBuffer] = {}
        self._max_events = max_events
        self._queue_size = queue_size
        self._exporters = exporters or []

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
        for exporter in self._exporters:
            try:
                exporter.emit(event)
            except Exception:
                # Exporter failures should not break streaming.
                pass
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
        history = list(buffer.history)
        for event in history:
            yield event
        if history:
            last = history[-1]
            if last.stream == StreamChannel.LIFECYCLE and last.event in {"end", "error", "timeout", "canceled"}:
                return
        # Drain any existing queued events to avoid duplicates of history.
        while not buffer.queue.empty():
            try:
                buffer.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        while True:
            event = await buffer.queue.get()
            yield event
            if event.stream == StreamChannel.LIFECYCLE and event.event in {"end", "error", "timeout", "canceled"}:
                break
