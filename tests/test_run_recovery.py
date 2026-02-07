"""Tests for run recovery after restart."""

import os
import tempfile

from agent_sdk.observability.stream_envelope import (
    RunMetadata,
    RunStatus,
    SessionMetadata,
    StreamChannel,
    StreamEnvelope,
)
from agent_sdk.storage.sqlite import SQLiteStorage


def test_recover_in_flight_runs_updates_status_and_events():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "recovery.db")
        storage = SQLiteStorage(db_path)
        storage.create_session(SessionMetadata(session_id="sess_recovery"))
        storage.create_run(
            RunMetadata(
                run_id="run_recovery",
                session_id="sess_recovery",
                agent_id="agent",
                status=RunStatus.RUNNING,
                metadata={"note": "in-flight"},
            )
        )
        storage.append_event(
            StreamEnvelope(
                run_id="run_recovery",
                session_id="sess_recovery",
                stream=StreamChannel.LIFECYCLE,
                event="start",
                payload={"task": "demo"},
                seq=0,
                status=RunStatus.RUNNING.value,
                metadata={"org_id": "default"},
            )
        )

        recovered = storage.recover_in_flight_runs()
        assert recovered == 1

        run = storage.get_run("run_recovery")
        assert run is not None
        assert run.status == RunStatus.ERROR
        assert run.ended_at is not None
        assert run.metadata.get("recovered") is True

        events = storage.list_events("run_recovery")
        assert events[-1].event == "recovered"
        assert events[-1].status == RunStatus.ERROR.value
        assert events[-1].payload["reason"] == "server_restart"
