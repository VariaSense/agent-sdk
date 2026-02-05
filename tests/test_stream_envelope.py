"""
Tests for stream envelope schema and run/session metadata.
"""

from agent_sdk.observability.stream_envelope import (
    StreamChannel,
    RunStatus,
    RunMetadata,
    SessionMetadata,
    StreamEnvelope,
    new_run_id,
    new_session_id,
)


def test_new_ids_have_prefixes():
    run_id = new_run_id()
    session_id = new_session_id()

    assert run_id.startswith("run_")
    assert session_id.startswith("sess_")
    assert len(run_id) > len("run_")
    assert len(session_id) > len("sess_")


def test_run_metadata_defaults():
    meta = RunMetadata(run_id="run_123", session_id="sess_123", agent_id="agent_1")

    assert meta.status == RunStatus.ACCEPTED
    assert meta.created_at
    assert meta.started_at is None
    assert meta.ended_at is None


def test_session_metadata_defaults():
    session = SessionMetadata(session_id="sess_abc")

    assert session.session_id == "sess_abc"
    assert session.created_at
    assert session.updated_at
    assert session.tags == {}
    assert session.metadata == {}


def test_stream_envelope_to_dict_minimal():
    env = StreamEnvelope(
        run_id="run_1",
        session_id="sess_1",
        stream=StreamChannel.ASSISTANT,
        event="delta",
        payload={"text": "hi"},
    )

    data = env.to_dict()
    assert data["run_id"] == "run_1"
    assert data["session_id"] == "sess_1"
    assert data["stream"] == "assistant"
    assert data["event"] == "delta"
    assert data["payload"]["text"] == "hi"
    assert "timestamp" in data
    assert "seq" not in data
    assert "status" not in data
    assert "metadata" not in data


def test_stream_envelope_to_dict_optional_fields():
    env = StreamEnvelope(
        run_id="run_1",
        session_id="sess_1",
        stream=StreamChannel.TOOL,
        event="result",
        payload={"ok": True},
        seq=7,
        status="ok",
        metadata={"tool": "calc"},
    )

    data = env.to_dict()
    assert data["seq"] == 7
    assert data["status"] == "ok"
    assert data["metadata"]["tool"] == "calc"


def test_stream_envelope_sse_format():
    env = StreamEnvelope(
        run_id="run_1",
        session_id="sess_1",
        stream=StreamChannel.LIFECYCLE,
        event="start",
        payload={"status": "running"},
    )

    sse = env.to_sse()
    assert sse.startswith("data: ")
    assert "\"stream\": \"lifecycle\"" in sse
    assert "\"event\": \"start\"" in sse
