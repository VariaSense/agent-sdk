"""Tests for billing CLI export."""

import json

from typer.testing import CliRunner

from agent_sdk.cli.main import app
from agent_sdk.storage import SQLiteStorage
from agent_sdk.observability.stream_envelope import RunMetadata, RunStatus, SessionMetadata


def test_billing_cli_export(tmp_path, monkeypatch):
    db_path = tmp_path / "agent_sdk.db"
    storage = SQLiteStorage(str(db_path))
    storage.create_session(SessionMetadata(session_id="sess_1", org_id="default"))
    storage.create_run(
        RunMetadata(
            run_id="run_1",
            session_id="sess_1",
            agent_id="planner-executor",
            org_id="default",
            status=RunStatus.COMPLETED,
            tags={"project": "alpha"},
            metadata={"token_count": 12},
        )
    )
    monkeypatch.setenv("AGENT_SDK_DB_PATH", str(db_path))
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["billing", "export", "--group-by", "org_id,project", "--format", "json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output.strip())
    assert payload["count"] == 1
    row = payload["results"][0]
    assert row["org_id"] == "default"
    assert row["project"] == "alpha"
    assert row["token_count"] == 12
