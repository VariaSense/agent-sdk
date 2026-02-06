"""Tests for CLI doctor command wiring and checks."""

from agent_sdk.cli.main import app
from agent_sdk.cli.commands import collect_doctor_checks


def test_doctor_command_registered():
    group_names = [g.name for g in app.registered_groups]
    assert "doctor" in group_names


def test_collect_doctor_checks_valid_config(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
models:
  planner:
    name: planner
    provider: openai
    model_id: gpt-4
    temperature: 0.1
    max_tokens: 128
  executor:
    name: executor
    provider: openai
    model_id: gpt-4
    temperature: 0.1
    max_tokens: 128

rate_limits: []
agents:
  planner:
    model: planner
  executor:
    model: executor
        """.strip()
        + "\n"
    )

    checks = collect_doctor_checks(str(config_path))
    names = {c["name"] for c in checks}
    assert "config.exists" in names
    assert "config.load" in names
