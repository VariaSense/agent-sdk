"""Runtime adapter for third-party local agent CLIs."""

from __future__ import annotations

import json
import os
import re
import subprocess
from typing import Any, Iterable, Optional

from agent_sdk.contracts.external_agent import ExternalAgentCommand
from agent_sdk.contracts.runtime import ExecutionMetadata, RunEvent, RunRequest, RunResult
from agent_sdk.ports import AgentRuntimePort


ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class ExternalAgentRuntime(AgentRuntimePort):
    """Expose a local third-party agent command as an SDK runtime."""

    def __init__(self, command: ExternalAgentCommand):
        self.command = command

    @classmethod
    def codex(
        cls,
        *,
        executable: str = "codex",
        cwd: Optional[str] = None,
        model: Optional[str] = None,
        profile: Optional[str] = None,
        sandbox: str = "workspace-write",
        approval_policy: Optional[str] = None,
        timeout_seconds: int = 1800,
        ignore_user_config: bool = True,
        extra_args: Optional[Iterable[str]] = None,
    ) -> "ExternalAgentRuntime":
        """Build a runtime backed by `codex exec`."""

        args = ["exec", "--json", "--color", "never", "--skip-git-repo-check"]
        if ignore_user_config:
            args.append("--ignore-user-config")
        if model:
            args.extend(["--model", model])
        if profile:
            args.extend(["--profile", profile])
        if sandbox:
            args.extend(["--sandbox", sandbox])
        if approval_policy:
            args.extend(["-c", f"approval_policy={json.dumps(approval_policy)}"])
        if extra_args:
            for arg in extra_args:
                if arg == "--ignore-user-config" and arg in args:
                    continue
                args.append(arg)
        args.append("-")
        return cls(
            ExternalAgentCommand(
                provider="codex",
                executable=executable,
                args=args,
                cwd=cwd,
                timeout_seconds=timeout_seconds,
                prompt_mode="stdin",
                output_format="jsonl",
            )
        )

    def run(self, request: RunRequest) -> RunResult:
        events = [
            RunEvent(
                stream="lifecycle",
                event="started",
                payload={
                    "agent": request.agent.name,
                    "provider": self.command.provider,
                    "correlation_id": request.metadata.correlation_id,
                },
            )
        ]
        argv = self._argv(request.prompt)
        env = os.environ.copy()
        env.update(self.command.env)

        try:
            completed = subprocess.run(
                argv,
                input=request.prompt if self.command.prompt_mode == "stdin" else None,
                capture_output=True,
                text=True,
                cwd=self.command.cwd,
                env=env,
                timeout=self.command.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = self._clean(exc.stdout or "")
            stderr = self._clean(exc.stderr or "")
            events.extend(self._events_from_output(stdout, stderr))
            events.append(
                RunEvent(
                    stream="lifecycle",
                    event="timeout",
                    payload={
                        "agent": request.agent.name,
                        "provider": self.command.provider,
                        "correlation_id": request.metadata.correlation_id,
                        "timeout_seconds": self.command.timeout_seconds,
                    },
                )
            )
            return self._result(
                "timed_out",
                stdout.strip(),
                events,
                request.metadata,
                {
                    "argv": argv,
                    "provider": self.command.provider,
                    "runner": "agent_sdk.runtime.ExternalAgentRuntime",
                    "timeout_seconds": self.command.timeout_seconds,
                },
            )
        except OSError as exc:
            events.append(
                RunEvent(
                    stream="lifecycle",
                    event="failed",
                    payload={
                        "agent": request.agent.name,
                        "provider": self.command.provider,
                        "correlation_id": request.metadata.correlation_id,
                        "error": str(exc),
                    },
                )
            )
            return self._result(
                "failed",
                "",
                events,
                request.metadata,
                {
                    "argv": argv,
                    "provider": self.command.provider,
                    "runner": "agent_sdk.runtime.ExternalAgentRuntime",
                    "error": str(exc),
                },
            )

        stdout = self._clean(completed.stdout)
        stderr = self._clean(completed.stderr)
        events.extend(self._events_from_output(stdout, stderr))
        status = "completed" if completed.returncode == 0 else "failed"
        events.append(
            RunEvent(
                stream="lifecycle",
                event=status,
                payload={
                    "agent": request.agent.name,
                    "provider": self.command.provider,
                    "returncode": completed.returncode,
                    "correlation_id": request.metadata.correlation_id,
                },
            )
        )
        debug = {
            "argv": argv,
            "provider": self.command.provider,
            "returncode": completed.returncode,
            "runner": "agent_sdk.runtime.ExternalAgentRuntime",
        }
        response = self._extract_response(stdout, events)
        return self._result(status, response, events, request.metadata, debug)

    def _argv(self, prompt: str) -> list[str]:
        argv = [self.command.executable, *self.command.args]
        if self.command.prompt_mode == "argument":
            argv.append(prompt)
        return argv

    def _clean(self, value: str | bytes | None) -> str:
        if value is None:
            return ""
        text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
        return ANSI_PATTERN.sub("", text) if self.command.strip_ansi else text

    def _events_from_output(self, stdout: str, stderr: str) -> list[RunEvent]:
        events: list[RunEvent] = []
        if self.command.output_format == "jsonl":
            for raw_line in stdout.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    events.append(RunEvent(stream="stdout", event="line", payload={"text": raw_line}))
                    continue
                event_name = self._string_from_paths(
                    payload,
                    ("type",),
                    ("event",),
                    ("msg", "type"),
                    ("payload", "type"),
                )
                events.append(
                    RunEvent(
                        stream=self.command.provider,
                        event=event_name or "event",
                        payload={"raw": payload},
                    )
                )
        else:
            events.extend(
                RunEvent(stream="stdout", event="line", payload={"text": line})
                for line in stdout.splitlines()
                if line
            )

        events.extend(
            RunEvent(stream="stderr", event="line", payload={"text": line})
            for line in stderr.splitlines()
            if line
        )
        return events

    def _extract_response(self, stdout: str, events: list[RunEvent]) -> str:
        for stream in (self.command.provider, "stdout"):
            for event in reversed([event for event in events if event.stream == stream]):
                payload = event.payload.get("raw", event.payload)
                response = self._string_from_paths(
                    payload,
                    ("response",),
                    ("message",),
                    ("content",),
                    ("text",),
                    ("data", "response"),
                    ("data", "message"),
                    ("data", "content"),
                    ("data", "text"),
                    ("msg", "message"),
                    ("msg", "content"),
                    ("payload", "message"),
                    ("payload", "content"),
                    ("payload", "text"),
                    ("item", "text"),
                    ("item", "message"),
                    ("item", "content"),
                )
                if response:
                    return response
        return stdout.strip()

    def _string_from_paths(self, payload: Any, *paths: tuple[str, ...]) -> Optional[str]:
        for path in paths:
            value = payload
            for key in path:
                if not isinstance(value, dict) or key not in value:
                    value = None
                    break
                value = value[key]
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _result(
        self,
        status: str,
        response: str,
        events: list[RunEvent],
        metadata: ExecutionMetadata,
        debug: Optional[dict[str, Any]] = None,
    ) -> RunResult:
        return RunResult(
            status=status,
            response=response,
            events=events,
            metadata=ExecutionMetadata.model_validate(metadata.model_dump()),
            debug=debug or {
                "provider": self.command.provider,
                "runner": "agent_sdk.runtime.ExternalAgentRuntime",
            },
        )
