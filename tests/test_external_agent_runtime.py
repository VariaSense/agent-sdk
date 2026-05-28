import sys

from agent_sdk.contracts import AgentDefinition, ExecutionMetadata, ExternalAgentCommand, RunRequest
from agent_sdk.ports import AgentRuntimePort
from agent_sdk.runtime import ExternalAgentRuntime


def test_external_agent_runtime_wraps_text_command():
    command = ExternalAgentCommand(
        provider="demo",
        executable=sys.executable,
        args=[
            "-c",
            "import sys; prompt=sys.stdin.read().strip(); print('completed: ' + prompt)",
        ],
        output_format="text",
    )
    runtime = ExternalAgentRuntime(command)

    result = runtime.run(
        RunRequest(agent=AgentDefinition(name="demo-worker"), prompt="write project plan")
    )

    assert isinstance(runtime, AgentRuntimePort)
    assert result.status == "completed"
    assert result.response == "completed: write project plan"
    assert any(event.stream == "stdout" and event.payload["text"] == result.response for event in result.events)


def test_external_agent_runtime_maps_jsonl_events_to_run_events():
    code = (
        "import json, sys; "
        "prompt=sys.stdin.read().strip(); "
        "print(json.dumps({'type': 'agent_message', 'message': 'handled ' + prompt}))"
    )
    command = ExternalAgentCommand(
        provider="codexlike",
        executable=sys.executable,
        args=["-c", code],
        output_format="jsonl",
    )
    runtime = ExternalAgentRuntime(command)

    result = runtime.run(RunRequest(agent=AgentDefinition(name="codex-worker"), prompt="task 42"))

    assert result.status == "completed"
    assert result.response == "handled task 42"
    agent_events = [event for event in result.events if event.stream == "codexlike"]
    assert agent_events[0].event == "agent_message"
    assert agent_events[0].payload["raw"] == {"type": "agent_message", "message": "handled task 42"}


def test_external_agent_runtime_reports_process_failures():
    command = ExternalAgentCommand(
        provider="demo",
        executable=sys.executable,
        args=["-c", "import sys; print('bad output'); sys.exit(7)"],
        output_format="text",
    )
    runtime = ExternalAgentRuntime(command)

    result = runtime.run(RunRequest(agent=AgentDefinition(name="failing-worker"), prompt="task"))

    assert result.status == "failed"
    assert result.response == "bad output"
    assert result.debug["returncode"] == 7
    assert result.events[-1].event == "failed"


def test_external_agent_runtime_supports_argument_prompt_mode():
    command = ExternalAgentCommand(
        provider="demo",
        executable=sys.executable,
        args=["-c", "import sys; print(sys.argv[1])"],
        output_format="text",
        prompt_mode="argument",
    )
    runtime = ExternalAgentRuntime(command)

    result = runtime.run(RunRequest(agent=AgentDefinition(name="argv-worker"), prompt="from argv"))

    assert result.status == "completed"
    assert result.response == "from argv"


def test_external_agent_runtime_reports_missing_executable_with_metadata():
    command = ExternalAgentCommand(
        provider="missing",
        executable="agent-sdk-command-that-does-not-exist",
        output_format="text",
    )
    runtime = ExternalAgentRuntime(command)
    request = RunRequest(
        agent=AgentDefinition(name="missing-worker"),
        prompt="task",
        metadata=ExecutionMetadata(correlation_id="corr-1"),
    )

    result = runtime.run(request)

    assert result.status == "failed"
    assert result.response == ""
    assert result.debug["provider"] == "missing"
    assert result.debug["runner"] == "agent_sdk.runtime.ExternalAgentRuntime"
    assert result.events[-1].payload["correlation_id"] == "corr-1"


def test_external_agent_runtime_reports_timeout_with_partial_output():
    code = "import time; print('started', flush=True); time.sleep(5)"
    command = ExternalAgentCommand(
        provider="slow",
        executable=sys.executable,
        args=["-c", code],
        output_format="text",
        timeout_seconds=1,
    )
    runtime = ExternalAgentRuntime(command)

    result = runtime.run(RunRequest(agent=AgentDefinition(name="slow-worker"), prompt="task"))

    assert result.status == "timed_out"
    assert result.response == "started"
    assert result.debug["timeout_seconds"] == 1
    assert result.events[-1].event == "timeout"


def test_external_agent_runtime_keeps_non_json_lines_from_jsonl_output():
    code = "print('plain line')"
    command = ExternalAgentCommand(
        provider="codexlike",
        executable=sys.executable,
        args=["-c", code],
        output_format="jsonl",
    )
    runtime = ExternalAgentRuntime(command)

    result = runtime.run(RunRequest(agent=AgentDefinition(name="codex-worker"), prompt="task"))

    assert result.status == "completed"
    assert result.response == "plain line"
    assert any(event.stream == "stdout" and event.payload["text"] == "plain line" for event in result.events)


def test_codex_factory_builds_codex_exec_jsonl_runtime():
    runtime = ExternalAgentRuntime.codex(cwd="/tmp/workspace", model="gpt-5", profile="dev")

    assert runtime.command.provider == "codex"
    assert runtime.command.executable == "codex"
    assert runtime.command.cwd == "/tmp/workspace"
    assert runtime.command.output_format == "jsonl"
    assert runtime.command.prompt_mode == "stdin"
    assert runtime.command.args[:2] == ["exec", "--json"]
    assert runtime.command.args.count("--ignore-user-config") == 1
    assert "--model" in runtime.command.args
    assert "gpt-5" in runtime.command.args
    assert "--profile" in runtime.command.args
    assert "--ask-for-approval" not in runtime.command.args
    assert runtime.command.args[-1] == "-"


def test_codex_jsonl_extracts_nested_item_text():
    code = (
        "import json; "
        "print(json.dumps({'type': 'thread.started', 'thread_id': 't1'})); "
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'done'}}))"
    )
    command = ExternalAgentCommand(
        provider="codex",
        executable=sys.executable,
        args=["-c", code],
        output_format="jsonl",
    )
    runtime = ExternalAgentRuntime(command)

    result = runtime.run(RunRequest(agent=AgentDefinition(name="codex-worker"), prompt="task"))

    assert result.status == "completed"
    assert result.response == "done"


def test_response_extraction_ignores_stderr_after_agent_message():
    code = (
        "import json, sys; "
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'final answer'}})); "
        "print('warning from side channel', file=sys.stderr)"
    )
    command = ExternalAgentCommand(
        provider="codex",
        executable=sys.executable,
        args=["-c", code],
        output_format="jsonl",
    )
    runtime = ExternalAgentRuntime(command)

    result = runtime.run(RunRequest(agent=AgentDefinition(name="codex-worker"), prompt="task"))

    assert result.status == "completed"
    assert result.response == "final answer"


def test_codex_factory_deduplicates_ignore_user_config_extra_arg():
    runtime = ExternalAgentRuntime.codex(extra_args=["--ignore-user-config", "--ephemeral"])

    assert runtime.command.args.count("--ignore-user-config") == 1
    assert "--ephemeral" in runtime.command.args


def test_jsonl_response_extraction_prefers_agent_message_over_late_stdout():
    code = (
        "import json; "
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'final answer'}})); "
        "print('late diagnostic')"
    )
    command = ExternalAgentCommand(
        provider="codex",
        executable=sys.executable,
        args=["-c", code],
        output_format="jsonl",
    )
    runtime = ExternalAgentRuntime(command)

    result = runtime.run(RunRequest(agent=AgentDefinition(name="codex-worker"), prompt="task"))

    assert result.status == "completed"
    assert result.response == "final answer"
    assert any(event.stream == "stdout" and event.payload["text"] == "late diagnostic" for event in result.events)
