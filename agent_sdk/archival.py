from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Dict, Any

from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    RunStatus,
    SessionMetadata,
    StreamEnvelope,
    StreamChannel,
)
from agent_sdk.storage.base import StorageBackend


class LocalArchiveBackend:
    def __init__(self, root: str = "archives") -> None:
        self._root = root
        os.makedirs(self._root, exist_ok=True)

    def export_run(self, storage: StorageBackend, run_id: str) -> str:
        run = storage.get_run(run_id)
        if not run:
            raise ValueError("run not found")
        events = storage.list_events(run_id, limit=10000)
        payload: Dict[str, Any] = {
            "run": asdict(run),
            "events": [event.to_dict() for event in events],
        }
        path = os.path.join(self._root, f"run_{run_id}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return path

    def export_session(self, storage: StorageBackend, session_id: str) -> str:
        session = storage.get_session(session_id)
        if not session:
            raise ValueError("session not found")
        runs = [run for run in storage.list_runs(org_id=None, limit=10000) if run.session_id == session_id]
        payload: Dict[str, Any] = {
            "session": asdict(session),
            "runs": [asdict(run) for run in runs],
        }
        path = os.path.join(self._root, f"session_{session_id}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return path

    def restore(self, storage: StorageBackend, path: str) -> None:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if "session" in payload:
            session = SessionMetadata(**payload["session"])
            storage.create_session(session)
        if "run" in payload:
            run = RunMetadata(**_normalize_run_payload(payload["run"]))
            storage.create_run(run)
            for event_payload in payload.get("events", []):
                event = StreamEnvelope(
                    run_id=event_payload["run_id"],
                    session_id=event_payload["session_id"],
                    stream=StreamChannel(event_payload["stream"]),
                    event=event_payload["event"],
                    payload=event_payload["payload"],
                    timestamp=event_payload.get("timestamp"),
                    seq=event_payload.get("seq"),
                    status=event_payload.get("status"),
                    metadata=event_payload.get("metadata", {}),
                )
                storage.append_event(event)
        if "runs" in payload:
            for run_payload in payload["runs"]:
                storage.create_run(RunMetadata(**_normalize_run_payload(run_payload)))


def _normalize_run_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(payload)
    status = normalized.get("status")
    if isinstance(status, str):
        try:
            normalized["status"] = RunStatus(status)
        except ValueError:
            normalized["status"] = RunStatus.ACCEPTED
    return normalized
