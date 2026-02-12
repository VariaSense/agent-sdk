"""Golden contract fixtures for API and event schemas."""

import json
from pathlib import Path

from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    RunStatus,
    SessionMetadata,
    StreamEnvelope,
    StreamChannel,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "contracts"


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_session_metadata_fixture_roundtrip():
    payload = _load("session_metadata.json")
    session = SessionMetadata(**payload)
    assert session.session_id == payload["session_id"]
    assert session.tags["tier"] == "standard"


def test_run_metadata_fixture_roundtrip():
    payload = _load("run_metadata.json")
    payload["status"] = RunStatus(payload["status"])
    run = RunMetadata(**payload)
    assert run.run_id == payload["run_id"]
    assert run.status.value == "running"


def test_event_envelope_fixture_roundtrip():
    payload = _load("event_envelope.json")
    envelope = StreamEnvelope(
        run_id=payload["run_id"],
        session_id=payload["session_id"],
        stream=StreamChannel(payload["stream"]),
        event=payload["event"],
        payload=payload["payload"],
        timestamp=payload["timestamp"],
        seq=payload["seq"],
        status=payload["status"],
        metadata=payload["metadata"],
    )
    data = envelope.to_dict()
    assert data["stream"] == payload["stream"]
    assert data["event"] == payload["event"]
