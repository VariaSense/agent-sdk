"""Tests for run/session retention pruning."""

from datetime import datetime, timezone, timedelta

from agent_sdk.storage.sqlite import SQLiteStorage
from agent_sdk.observability.stream_envelope import SessionMetadata, RunMetadata, RunStatus


def test_prune_runs_and_sessions(tmp_path):
    db_path = tmp_path / "retention.db"
    storage = SQLiteStorage(str(db_path))
    past = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    session_old = SessionMetadata(session_id="sess_old", org_id="default", created_at=past, updated_at=past)
    session_new = SessionMetadata(session_id="sess_new", org_id="default")
    storage.create_session(session_old)
    storage.create_session(session_new)
    run_old = RunMetadata(
        run_id="run_old",
        session_id="sess_old",
        agent_id="agent",
        org_id="default",
        status=RunStatus.ACCEPTED,
        created_at=past,
    )
    storage.create_run(run_old)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    pruned_runs = storage.prune_runs("default", cutoff)
    pruned_sessions = storage.prune_sessions("default", cutoff)
    assert pruned_runs >= 1
    assert pruned_sessions >= 1
