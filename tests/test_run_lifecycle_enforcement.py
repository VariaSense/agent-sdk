"""Tests for run lifecycle transition enforcement."""

from agent_sdk.observability.stream_envelope import RunMetadata, RunStatus
from agent_sdk.storage.sqlite import SQLiteStorage


def test_invalid_run_transition_raises(tmp_path):
    db_path = tmp_path / "runs.db"
    storage = SQLiteStorage(str(db_path))
    run = RunMetadata(
        run_id="run_1",
        session_id="session_1",
        agent_id="planner",
        org_id="default",
        status=RunStatus.RUNNING,
    )
    storage.create_run(run)
    completed = RunMetadata(
        run_id="run_1",
        session_id="session_1",
        agent_id="planner",
        org_id="default",
        status=RunStatus.COMPLETED,
    )
    storage.update_run(completed)
    invalid = RunMetadata(
        run_id="run_1",
        session_id="session_1",
        agent_id="planner",
        org_id="default",
        status=RunStatus.RUNNING,
    )
    try:
        storage.update_run(invalid)
    except ValueError as exc:
        assert "Invalid run status transition" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid transition")
