"""Run log exporters for structured JSONL logs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, TextIO, List
import json
import os
import threading
import sys

from agent_sdk.observability.stream_envelope import StreamEnvelope


class RunLogExporter(ABC):
    """Base class for run log exporters."""

    @abstractmethod
    def emit(self, event: StreamEnvelope) -> None:
        """Emit a run event."""


@dataclass
class JSONLFileExporter(RunLogExporter):
    """Write run events to a JSONL file."""

    path: str

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

    def emit(self, event: StreamEnvelope) -> None:
        line = event.to_json()
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")


class StdoutExporter(RunLogExporter):
    """Emit run events to stdout as JSONL."""

    def __init__(self, stream: Optional[TextIO] = None) -> None:
        self._stream = stream or sys.stdout
        self._lock = threading.Lock()

    def emit(self, event: StreamEnvelope) -> None:
        line = event.to_json()
        with self._lock:
            self._stream.write(line + "\n")


def create_run_log_exporters(
    path: Optional[str] = None, emit_stdout: bool = False
) -> List[RunLogExporter]:
    exporters: List[RunLogExporter] = []
    if path:
        exporters.append(JSONLFileExporter(path=path))
    if emit_stdout:
        exporters.append(StdoutExporter())
    return exporters
