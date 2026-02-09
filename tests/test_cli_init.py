"""Tests for CLI project scaffolding."""

from typer.testing import CliRunner
from agent_sdk.cli.main import app


def test_cli_init_creates_project(tmp_path):
    runner = CliRunner()
    result = runner.invoke(app, ["init", "--name", str(tmp_path / "demo")])
    assert result.exit_code == 0
    assert (tmp_path / "demo" / "config.yaml").exists()
    assert (tmp_path / "demo" / "tools.py").exists()
    assert (tmp_path / "demo" / ".env.example").exists()
