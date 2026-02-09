"""Audit log exporters for admin and security actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TextIO
import json
import os
import threading
import sys
from datetime import datetime, timezone

from agent_sdk.observability.redaction import Redactor


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AuditLogEntry:
    action: str
    actor: str
    org_id: str
    target_type: str
    target_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "action": self.action,
            "actor": self.actor,
            "org_id": self.org_id,
            "target_type": self.target_type,
            "timestamp": self.timestamp,
        }
        if self.target_id:
            payload["target_id"] = self.target_id
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class AuditLogExporter:
    def emit(self, entry: AuditLogEntry) -> None:
        raise NotImplementedError


@dataclass
class JSONLAuditExporter(AuditLogExporter):
    path: str

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

    def emit(self, entry: AuditLogEntry) -> None:
        line = entry.to_json()
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")


class StdoutAuditExporter(AuditLogExporter):
    def __init__(self, stream: Optional[TextIO] = None) -> None:
        self._stream = stream or sys.stdout
        self._lock = threading.Lock()

    def emit(self, entry: AuditLogEntry) -> None:
        line = entry.to_json()
        with self._lock:
            self._stream.write(line + "\n")


class AuditLogger:
    def __init__(
        self,
        exporters: Optional[List[AuditLogExporter]] = None,
        redactor: Optional["Redactor"] = None,
    ) -> None:
        self._exporters = exporters or []
        self._redactor = redactor

    def emit(self, entry: AuditLogEntry) -> None:
        if self._redactor and self._redactor.enabled and entry.metadata:
            entry = AuditLogEntry(
                action=entry.action,
                actor=entry.actor,
                org_id=entry.org_id,
                target_type=entry.target_type,
                target_id=entry.target_id,
                metadata=self._redactor.redact_metadata(entry.metadata),
                timestamp=entry.timestamp,
            )
        for exporter in self._exporters:
            try:
                exporter.emit(entry)
            except Exception:
                pass


def create_audit_loggers(
    path: Optional[str] = None,
    emit_stdout: bool = False,
    redactor: Optional["Redactor"] = None,
) -> AuditLogger:
    exporters: List[AuditLogExporter] = []
    if path:
        exporters.append(JSONLAuditExporter(path=path))
    if emit_stdout:
        exporters.append(StdoutAuditExporter())
    return AuditLogger(exporters=exporters, redactor=redactor)
