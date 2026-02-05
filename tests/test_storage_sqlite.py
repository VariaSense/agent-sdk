"""
Tests for SQLiteStorage backend.
"""

import os
import tempfile

from agent_sdk.storage.sqlite import SQLiteStorage
from agent_sdk.observability.stream_envelope import (
    SessionMetadata,
    RunMetadata,
    RunStatus,
    StreamEnvelope,
    StreamChannel,
)


def test_sqlite_storage_sessions_runs_events():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "storage.db")
        storage = SQLiteStorage(db_path)

        session = SessionMetadata(session_id="sess_1", user_id="user_1")
        storage.create_session(session)
        loaded_session = storage.get_session("sess_1")

        assert loaded_session is not None
        assert loaded_session.session_id == "sess_1"
        assert loaded_session.user_id == "user_1"

        updated_session = SessionMetadata(
            session_id="sess_1",
            user_id="user_2",
            created_at=loaded_session.created_at,
            updated_at=loaded_session.updated_at,
            tags={"tier": "pro"},
            metadata={"note": "updated"},
        )
        storage.update_session(updated_session)
        loaded_updated = storage.get_session("sess_1")
        assert loaded_updated.user_id == "user_2"
        assert loaded_updated.tags["tier"] == "pro"

        run = RunMetadata(
            run_id="run_1",
            session_id="sess_1",
            agent_id="agent_1",
            status=RunStatus.ACCEPTED,
            model="mock",
        )
        storage.create_run(run)
        loaded_run = storage.get_run("run_1")
        assert loaded_run is not None
        assert loaded_run.run_id == "run_1"
        assert loaded_run.status == RunStatus.ACCEPTED

        updated_run = RunMetadata(
            run_id="run_1",
            session_id="sess_1",
            agent_id="agent_1",
            status=RunStatus.COMPLETED,
            model="mock",
            created_at=loaded_run.created_at,
            started_at=loaded_run.started_at,
            ended_at=loaded_run.ended_at,
            tags={"source": "test"},
            metadata={"ok": True},
        )
        storage.update_run(updated_run)
        loaded_updated_run = storage.get_run("run_1")
        assert loaded_updated_run.status == RunStatus.COMPLETED
        assert loaded_updated_run.tags["source"] == "test"

        event = StreamEnvelope(
            run_id="run_1",
            session_id="sess_1",
            stream=StreamChannel.ASSISTANT,
            event="delta",
            payload={"text": "hi"},
            seq=1,
            status="ok",
            metadata={"k": "v"},
        )
        storage.append_event(event)
        events = storage.list_events("run_1")

        assert len(events) == 1
        assert events[0].event == "delta"
        assert events[0].payload["text"] == "hi"
