"""Tests for compatibility CLI commands."""

from typer.testing import CliRunner

from agent_sdk.cli.main import app


runner = CliRunner()


def test_upgrade_check_command():
    result = runner.invoke(app, ["compat", "upgrade-check", "0.1.1", "--current", "0.1.0"])
    assert result.exit_code == 0
    assert "compatible" in result.stdout
