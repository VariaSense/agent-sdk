"""Tests for billing chargeback aggregation."""

from agent_sdk.billing import generate_chargeback_report
from agent_sdk.observability.stream_envelope import RunMetadata, RunStatus


def test_chargeback_report_groups_by_project():
    runs = [
        RunMetadata(
            run_id="run_1",
            session_id="sess_1",
            agent_id="planner-executor",
            org_id="default",
            status=RunStatus.COMPLETED,
            tags={"project": "alpha"},
            metadata={"token_count": 10, "cost_usd": 0.5},
        ),
        RunMetadata(
            run_id="run_2",
            session_id="sess_1",
            agent_id="planner-executor",
            org_id="default",
            status=RunStatus.COMPLETED,
            tags={"project": "alpha"},
            metadata={"token_count": 5},
        ),
        RunMetadata(
            run_id="run_3",
            session_id="sess_2",
            agent_id="planner-executor",
            org_id="default",
            status=RunStatus.COMPLETED,
            tags={"project": "beta"},
            metadata={"token_count": 7, "cost": 1.2},
        ),
    ]

    report = generate_chargeback_report(runs, group_by="org_id,project")
    by_project = {row["project"]: row for row in report}

    assert by_project["alpha"]["run_count"] == 2
    assert by_project["alpha"]["session_count"] == 1
    assert by_project["alpha"]["token_count"] == 15
    assert by_project["alpha"]["cost_usd"] == 0.5

    assert by_project["beta"]["run_count"] == 1
    assert by_project["beta"]["session_count"] == 1
    assert by_project["beta"]["token_count"] == 7
    assert by_project["beta"]["cost_usd"] == 1.2
