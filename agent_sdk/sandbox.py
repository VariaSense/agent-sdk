"""Tool sandbox interfaces."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Callable, Any

from agent_sdk.exceptions import ToolError


class ToolSandbox:
    def run(self, tool: Callable[[dict], Any], inputs: dict) -> Any:
        raise NotImplementedError


@dataclass
class LocalToolSandbox(ToolSandbox):
    timeout_seconds: float = 10.0

    def run(self, tool: Callable[[dict], Any], inputs: dict) -> Any:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(tool, inputs)
            try:
                return future.result(timeout=self.timeout_seconds)
            except TimeoutError as exc:
                raise ToolError("Tool execution timed out") from exc


class DockerToolSandbox(ToolSandbox):
    def run(self, tool: Callable[[dict], Any], inputs: dict) -> Any:
        raise ToolError("Docker sandbox not configured")
