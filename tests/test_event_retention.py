"""Tests for event retention policies."""

import os
import tempfile

from agent_sdk.observability.event_retention import EventRetentionPolicy
from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    RunStatus,
    SessionMetadata,
    StreamChannel,
    StreamEnvelope,
)
from agent_sdk.server.run_store import RunEventStore
from agent_sdk.storage.sqlite import SQLiteStorage


def _append_events(storage: SQLiteStorage, run_id: str, session_id: str, count: int) -> None:
    for seq in range(count):
        storage.append_event(
            StreamEnvelope(
                run_id=run_id,
                session_id=session_id,
                stream=StreamChannel.ASSISTANT,
                event="message",
                payload={"text": f"msg-{seq}"},
                seq=seq,
                status=RunStatus.RUNNING.value,
                metadata={"org_id": "default"},
            )
        )


def test_sqlite_delete_events_by_seq():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "retention.db")
        storage = SQLiteStorage(db_path)
        storage.create_session(SessionMetadata(session_id="sess_retention"))
        storage.create_run(
            RunMetadata(
                run_id="run_retention",
                session_id="sess_retention",
                agent_id="agent",
                status=RunStatus.RUNNING,
            )
        )

        _append_events(storage, "run_retention", "sess_retention", 5)
        deleted = storage.delete_events("run_retention", before_seq=3)
        remaining = storage.list_events("run_retention")

        assert deleted == 3
        assert [event.seq for event in remaining] == [3, 4]


def test_run_store_enforces_retention_policy():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "retention_store.db")
        storage = SQLiteStorage(db_path)
        storage.create_session(SessionMetadata(session_id="sess_policy"))
        storage.create_run(
            RunMetadata(
                run_id="run_policy",
                session_id="sess_policy",
                agent_id="agent",
                status=RunStatus.RUNNING,
            )
        )

        policy = EventRetentionPolicy(max_events=2, enabled=True)
        run_store = RunEventStore(storage=storage, retention_policy=policy)

        for seq in range(4):
            run_store.append_event(
                "run_policy",
                StreamEnvelope(
                    run_id="run_policy",
                    session_id="sess_policy",
                    stream=StreamChannel.ASSISTANT,
                    event="message",
                    payload={"text": f"msg-{seq}"},
                    seq=seq,
                    status=RunStatus.RUNNING.value,
                    metadata={"org_id": "default"},
                ),
            )

        remaining = storage.list_events("run_policy")
        assert [event.seq for event in remaining] == [2, 3]
