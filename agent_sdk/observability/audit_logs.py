"""Audit log exporters for admin and security actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TextIO
import json
import os
import threading
import sys
from datetime import datetime, timezone
import hashlib
from urllib import request as urlrequest

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
    prev_hash: Optional[str] = None
    hash: Optional[str] = None

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
        if self.prev_hash:
            payload["prev_hash"] = self.prev_hash
        if self.hash:
            payload["hash"] = self.hash
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    def to_hash_payload(self, prev_hash: Optional[str]) -> Dict[str, Any]:
        payload = self.to_dict()
        payload.pop("hash", None)
        if prev_hash:
            payload["prev_hash"] = prev_hash
        else:
            payload.pop("prev_hash", None)
        return payload


class AuditHashChain:
    def __init__(self, seed: Optional[str] = None) -> None:
        self._last_hash = seed

    @property
    def last_hash(self) -> Optional[str]:
        return self._last_hash

    def apply(self, entry: AuditLogEntry) -> AuditLogEntry:
        prev_hash = self._last_hash
        payload = entry.to_hash_payload(prev_hash)
        payload_json = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        digest = hashlib.sha256(payload_json).hexdigest()
        self._last_hash = digest
        return AuditLogEntry(
            action=entry.action,
            actor=entry.actor,
            org_id=entry.org_id,
            target_type=entry.target_type,
            target_id=entry.target_id,
            metadata=entry.metadata,
            timestamp=entry.timestamp,
            prev_hash=prev_hash,
            hash=digest,
        )

    @staticmethod
    def load_last_hash(path: str) -> Optional[str]:
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    return None
                pos = handle.tell() - 1
                while pos > 0:
                    handle.seek(pos)
                    if handle.read(1) == b"\n":
                        break
                    pos -= 1
                handle.seek(pos + 1)
                last_line = handle.readline().decode("utf-8").strip()
            if not last_line:
                return None
            payload = json.loads(last_line)
            return payload.get("hash")
        except Exception:
            return None


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


class HttpAuditExporter(AuditLogExporter):
    def __init__(self, url: str, timeout_seconds: float = 5.0) -> None:
        self._url = url
        self._timeout = timeout_seconds
        self._lock = threading.Lock()

    def emit(self, entry: AuditLogEntry) -> None:
        payload = entry.to_json().encode("utf-8")
        req = urlrequest.Request(
            self._url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._lock:
            with urlrequest.urlopen(req, timeout=self._timeout):
                pass


class AuditLogger:
    def __init__(
        self,
        exporters: Optional[List[AuditLogExporter]] = None,
        redactor: Optional["Redactor"] = None,
        hash_chain: Optional[AuditHashChain] = None,
    ) -> None:
        self._exporters = exporters or []
        self._redactor = redactor
        self._hash_chain = hash_chain

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
        if self._hash_chain:
            entry = self._hash_chain.apply(entry)
        for exporter in self._exporters:
            try:
                exporter.emit(entry)
            except Exception:
                pass


def create_audit_loggers(
    path: Optional[str] = None,
    emit_stdout: bool = False,
    redactor: Optional["Redactor"] = None,
    hash_chain: Optional[AuditHashChain] = None,
    http_endpoint: Optional[str] = None,
    http_timeout_seconds: float = 5.0,
    extra_exporters: Optional[List[AuditLogExporter]] = None,
) -> AuditLogger:
    exporters: List[AuditLogExporter] = []
    if path:
        exporters.append(JSONLAuditExporter(path=path))
    if emit_stdout:
        exporters.append(StdoutAuditExporter())
    if http_endpoint:
        exporters.append(HttpAuditExporter(url=http_endpoint, timeout_seconds=http_timeout_seconds))
    if extra_exporters:
        exporters.extend(extra_exporters)
    return AuditLogger(exporters=exporters, redactor=redactor, hash_chain=hash_chain)
