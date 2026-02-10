"""Tests for compliance report CLI."""

from typer.testing import CliRunner
import os

from agent_sdk.cli.main import app


def test_compliance_report_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_SDK_CONTROL_PLANE_DB_PATH", os.path.join(tmp_path, "control_plane.db"))
    runner = CliRunner()
    output = tmp_path / "report.zip"
    result = runner.invoke(app, ["compliance-report", "report", "--output", str(output)])
    assert result.exit_code == 0
    assert output.exists()
