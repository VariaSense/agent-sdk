#!/usr/bin/env bash
set -e

echo "Creating agent-sdk directory tree and populating full SDK code..."

# Root package
mkdir -p agent_sdk
cat << 'EOF' > agent_sdk/__init__.py
from .core.agent import Agent
from .core.context import AgentContext
from .core.tools import Tool, ToolRegistry, tool, GLOBAL_TOOL_REGISTRY
from .core.runtime import PlannerExecutorRuntime

from .planning.planner import PlannerAgent
from .planning.plan_schema import Plan, PlanStep

from .execution.executor import ExecutorAgent

from .llm.base import LLMClient, LLMResponse
from .llm.mock import MockLLMClient

from .config.model_config import ModelConfig
from .config.rate_limit import RateLimitRule, RateLimiter

from .observability.bus import EventBus
from .observability.sinks import ConsoleSink, JSONLSink
from .observability.events import ObsEvent

from .plugins.loader import PluginLoader
EOF

################################
# core/
################################
mkdir -p agent_sdk/core

cat << 'EOF' > agent_sdk/core/__init__.py
EOF

cat << 'EOF' > agent_sdk/core/messages.py
from dataclasses import dataclass, field
from typing import Any, Dict
import uuid

@dataclass
class Message:
    id: str
    role: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

def make_message(role: str, content: str, metadata=None) -> Message:
    return Message(
        id=str(uuid.uuid4()),
        role=role,
        content=content,
        metadata=metadata or {},
    )
EOF

cat << 'EOF' > agent_sdk/core/tools.py
from dataclasses import dataclass
from typing import Callable, Dict, Any, List

@dataclass
class Tool:
    name: str
    description: str
    func: Callable[[Dict[str, Any]], Any]

    def __call__(self, args: Dict[str, Any]) -> Any:
        return self.func(args)

    async def call_async(self, args: Dict[str, Any]) -> Any:
        import inspect, asyncio
        if inspect.iscoroutinefunction(self.func):
            return await self.func(args)
        return await asyncio.to_thread(self.func, args)

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    @property
    def tools(self) -> Dict[str, Tool]:
        return self._tools

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

GLOBAL_TOOL_REGISTRY = ToolRegistry()

def tool(name: str, description: str):
    def decorator(func):
        t = Tool(name=name, description=description, func=func)
        GLOBAL_TOOL_REGISTRY.register(t)
        return func
    return decorator
EOF

cat << 'EOF' > agent_sdk/core/agent.py
from abc import ABC, abstractmethod
from .messages import Message

class Agent(ABC):
    def __init__(self, name: str, context: "AgentContext"):
        self.name = name
        self.context = context

    @abstractmethod
    def step(self, incoming: Message) -> Message:
        ...

    async def step_async(self, incoming: Message) -> Message:
        import asyncio
        return await asyncio.to_thread(self.step, incoming)
EOF

cat << 'EOF' > agent_sdk/core/context.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from .messages import Message
from .tools import Tool
from agent_sdk.config.model_config import ModelConfig
from agent_sdk.config.rate_limit import RateLimiter
from agent_sdk.observability.bus import EventBus

@dataclass
class AgentContext:
    short_term: List[Message] = field(default_factory=list)
    long_term: List[Message] = field(default_factory=list)
    tools: Dict[str, Tool] = field(default_factory=dict)
    model_config: Optional[ModelConfig] = None
    config: Dict[str, Any] = field(default_factory=dict)
    events: Optional[EventBus] = None
    rate_limiter: Optional[RateLimiter] = None
EOF

cat << 'EOF' > agent_sdk/core/runtime.py
from typing import List
from .messages import Message, make_message
from agent_sdk.planning.planner import PlannerAgent
from agent_sdk.execution.executor import ExecutorAgent

class PlannerExecutorRuntime:
    def __init__(self, planner: PlannerAgent, executor: ExecutorAgent):
        self.planner = planner
        self.executor = executor

    def run(self, task_text: str) -> List[Message]:
        task_msg = make_message("user", task_text)
        plan_msg = self.planner.step(task_msg)
        exec_msg = self.executor.step(plan_msg)
        return [plan_msg, exec_msg]

    async def run_async(self, task_text: str) -> List[Message]:
        task_msg = make_message("user", task_text)
        plan_msg = await self.planner.step_async(task_msg)
        exec_msg = await self.executor.step_async(plan_msg)
        return [plan_msg, exec_msg]
EOF

################################
# config/
################################
mkdir -p agent_sdk/config

cat << 'EOF' > agent_sdk/config/__init__.py
EOF

cat << 'EOF' > agent_sdk/config/model_config.py
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ModelConfig:
    name: str
    provider: str
    model_id: str
    temperature: float = 0.2
    max_tokens: int = 1024
    extra: Dict[str, Any] = None
EOF

cat << 'EOF' > agent_sdk/config/rate_limit.py
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from collections import defaultdict, deque
import time

@dataclass
class RateLimitRule:
    name: str
    max_calls: Optional[int] = None
    max_tokens: Optional[int] = None
    window_seconds: int = 60
    scope: str = "model"  # "model", "agent", "tenant"

class RateLimiter:
    def __init__(self, rules: List[RateLimitRule]):
        self.rules = rules
        self.call_history: Dict[str, deque] = defaultdict(deque)
        self.token_history: Dict[str, deque[Tuple[float, int]]] = defaultdict(deque)

    def _key(self, rule: RateLimitRule, agent: str, model: str, tenant: str) -> str:
        if rule.scope == "model":
            return f"model:{model}"
        if rule.scope == "agent":
            return f"agent:{agent}"
        if rule.scope == "tenant":
            return f"tenant:{tenant}"
        return "global"

    def check(self, agent: str, model: str, tokens: int, tenant: str = "default"):
        now = time.time()
        for rule in self.rules:
            key = self._key(rule, agent, model, tenant)

            while self.call_history[key] and now - self.call_history[key][0] > rule.window_seconds:
                self.call_history[key].popleft()
            while self.token_history[key] and now - self.token_history[key][0][0] > rule.window_seconds:
                self.token_history[key].popleft()

            if rule.max_calls is not None and len(self.call_history[key]) >= rule.max_calls:
                raise Exception(f"Rate limit exceeded: {rule.name} (calls)")

            if rule.max_tokens is not None:
                used = sum(t for _, t in self.token_history[key])
                if used + tokens > rule.max_tokens:
                    raise Exception(f"Rate limit exceeded: {rule.name} (tokens)")

        for rule in self.rules:
            key = self._key(rule, agent, model, tenant)
            self.call_history[key].append(now)
            self.token_history[key].append((now, tokens))
EOF

cat << 'EOF' > agent_sdk/config/loader.py
import yaml
from agent_sdk import (
    ModelConfig, RateLimitRule, RateLimiter,
    PlannerAgent, ExecutorAgent,
    AgentContext, GLOBAL_TOOL_REGISTRY,
)
from agent_sdk.llm.base import LLMClient

def load_config(path: str, llm_client: LLMClient):
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)

    models = {
        name: ModelConfig(**m)
        for name, m in cfg.get("models", {}).items()
    }

    rules = [RateLimitRule(**r) for r in cfg.get("rate_limits", [])]
    rate_limiter = RateLimiter(rules)

    tools = GLOBAL_TOOL_REGISTRY.tools

    planner_cfg = cfg["agents"]["planner"]
    executor_cfg = cfg["agents"]["executor"]

    planner_context = AgentContext(
        tools=tools,
        model_config=models[planner_cfg["model"]],
        events=None,
        rate_limiter=rate_limiter,
    )

    executor_context = AgentContext(
        tools=tools,
        model_config=models[executor_cfg["model"]],
        events=None,
        rate_limiter=rate_limiter,
    )

    planner = PlannerAgent("planner", planner_context, llm_client)
    executor = ExecutorAgent("executor", executor_context, llm_client)

    return planner, executor
EOF

################################
# llm/
################################
mkdir -p agent_sdk/llm

cat << 'EOF' > agent_sdk/llm/__init__.py
EOF

cat << 'EOF' > agent_sdk/llm/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict
from agent_sdk.config.model_config import ModelConfig

@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMClient(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        ...

    async def generate_async(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        import asyncio
        return await asyncio.to_thread(self.generate, messages, model_config)
EOF

cat << 'EOF' > agent_sdk/llm/mock.py
from typing import List, Dict
from agent_sdk.config.model_config import ModelConfig
from .base import LLMClient, LLMResponse

class MockLLMClient(LLMClient):
    def generate(self, messages: List[Dict[str, str]], model_config: ModelConfig) -> LLMResponse:
        last = messages[-1]["content"]
        text = f"[{model_config.name}] {last}"
        prompt_tokens = sum(len(m["content"].split()) for m in messages)
        completion_tokens = len(text.split())
        total_tokens = prompt_tokens + completion_tokens
        return LLMResponse(text, prompt_tokens, completion_tokens, total_tokens)
EOF

################################
# planning/
################################
mkdir -p agent_sdk/planning

cat << 'EOF' > agent_sdk/planning/__init__.py
EOF

cat << 'EOF' > agent_sdk/planning/plan_schema.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class PlanStep:
    id: int
    description: str
    tool: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

@dataclass
class Plan:
    task: str
    steps: List[PlanStep] = field(default_factory=list)
EOF

cat << 'EOF' > agent_sdk/planning/planner.py
import json
import time
from typing import List, Dict
from agent_sdk.core.agent import Agent
from agent_sdk.core.messages import Message, make_message
from agent_sdk.observability.events import ObsEvent
from agent_sdk.planning.plan_schema import Plan, PlanStep

PLANNER_SYSTEM_PROMPT = """
You are a planning agent. Given a user task and a list of tools,
you break the task into a small number of ordered steps.

Respond ONLY with valid JSON:
{
  "task": "...",
  "steps": [
    {"id": 1, "description": "...", "tool": "optional_or_null", "inputs": {...}, "notes": "optional"}
  ]
}
"""

class PlannerAgent(Agent):
    def __init__(self, name: str, context, llm):
        super().__init__(name, context)
        self.llm = llm

    def _build_prompt(self, task: str) -> List[Dict[str, str]]:
        tools_desc = "\n".join(
            f"- {t.name}: {t.description}"
            for t in self.context.tools.values()
        ) or "None"

        user_prompt = f"User task:\n{task}\n\nAvailable tools:\n{tools_desc}"
        return [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ]

    def plan(self, task: str) -> Plan:
        if self.context.events:
            self.context.events.emit(ObsEvent("planner.start", self.name, {"task": task}))

        prompt = self._build_prompt(task)
        tokens_estimate = sum(len(m["content"].split()) for m in prompt)

        if self.context.rate_limiter and self.context.model_config:
            self.context.rate_limiter.check(self.name, self.context.model_config.name, tokens_estimate)

        start = time.time()
        resp = self.llm.generate(prompt, self.context.model_config)
        end = time.time()
        latency_ms = (end - start) * 1000

        if self.context.events and self.context.model_config:
            self.context.events.emit(ObsEvent("llm.latency", self.name,
                                              {"model": self.context.model_config.name, "latency_ms": latency_ms}))
            self.context.events.emit(ObsEvent("llm.usage", self.name,
                                              {"model": self.context.model_config.name,
                                               "prompt_tokens": resp.prompt_tokens,
                                               "completion_tokens": resp.completion_tokens,
                                               "total_tokens": resp.total_tokens}))

        raw = resp.text
        if self.context.events:
            self.context.events.emit(ObsEvent("planner.raw_output", self.name, {"raw": raw}))

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            plan = Plan(task=task, steps=[PlanStep(id=1, description=raw)])
        else:
            plan = Plan(
                task=data.get("task", task),
                steps=[
                    PlanStep(
                        id=s.get("id"),
                        description=s.get("description", ""),
                        tool=s.get("tool"),
                        inputs=s.get("inputs"),
                        notes=s.get("notes"),
                    )
                    for s in data.get("steps", [])
                ],
            )

        if self.context.events:
            self.context.events.emit(ObsEvent("planner.complete", self.name, {"steps": len(plan.steps)}))

        return plan

    def step(self, incoming: Message) -> Message:
        plan = self.plan(incoming.content)
        content = json.dumps(
            {
                "task": plan.task,
                "steps": [
                    {
                        "id": s.id,
                        "description": s.description,
                        "tool": s.tool,
                        "inputs": s.inputs,
                        "notes": s.notes,
                    }
                    for s in plan.steps
                ],
            },
            indent=2,
        )
        reply = make_message("agent", content, metadata={"type": "plan"})
        self.context.short_term.append(incoming)
        self.context.short_term.append(reply)
        return reply

    async def plan_async(self, task: str) -> Plan:
        prompt = self._build_prompt(task)
        tokens_estimate = sum(len(m["content"].split()) for m in prompt)

        if self.context.rate_limiter and self.context.model_config:
            self.context.rate_limiter.check(self.name, self.context.model_config.name, tokens_estimate)

        import time as _t
        start = _t.time()
        resp = await self.llm.generate_async(prompt, self.context.model_config)
        end = _t.time()
        latency_ms = (end - start) * 1000

        if self.context.events and self.context.model_config:
            self.context.events.emit(ObsEvent("llm.latency", self.name,
                                              {"model": self.context.model_config.name, "latency_ms": latency_ms}))
            self.context.events.emit(ObsEvent("llm.usage", self.name,
                                              {"model": self.context.model_config.name,
                                               "prompt_tokens": resp.prompt_tokens,
                                               "completion_tokens": resp.completion_tokens,
                                               "total_tokens": resp.total_tokens}))

        raw = resp.text
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return Plan(task=task, steps=[PlanStep(id=1, description=raw)])
        return Plan(
            task=data.get("task", task),
            steps=[
                PlanStep(
                    id=s.get("id"),
                    description=s.get("description", ""),
                    tool=s.get("tool"),
                    inputs=s.get("inputs"),
                    notes=s.get("notes"),
                )
                for s in data.get("steps", [])
            ],
        )

    async def step_async(self, incoming: Message) -> Message:
        plan = await self.plan_async(incoming.content)
        import json as _json
        content = _json.dumps(
            {
                "task": plan.task,
                "steps": [
                    {
                        "id": s.id,
                        "description": s.description,
                        "tool": s.tool,
                        "inputs": s.inputs,
                        "notes": s.notes,
                    }
                    for s in plan.steps
                ],
            },
            indent=2,
        )
        reply = make_message("agent", content, metadata={"type": "plan"})
        self.context.short_term.append(incoming)
        self.context.short_term.append(reply)
        return reply
EOF

################################
# execution/
################################
mkdir -p agent_sdk/execution

cat << 'EOF' > agent_sdk/execution/__init__.py
EOF

cat << 'EOF' > agent_sdk/execution/step_result.py
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class StepResult:
    step_id: int
    success: bool
    output: Any
    error: Optional[str] = None
EOF

cat << 'EOF' > agent_sdk/execution/executor.py
import json
import time
from agent_sdk.core.agent import Agent
from agent_sdk.core.messages import Message, make_message
from agent_sdk.observability.events import ObsEvent
from agent_sdk.planning.plan_schema import Plan, PlanStep
from .step_result import StepResult

EXECUTOR_SYSTEM_PROMPT = """
You are an execution agent. You receive:
- a high-level task
- the current step description
- the tool output (if any)

You produce a short textual result for this step.
"""

class ExecutorAgent(Agent):
    def __init__(self, name: str, context, llm):
        super().__init__(name, context)
        self.llm = llm

    def _run_tool(self, step: PlanStep) -> StepResult:
        if self.context.events:
            self.context.events.emit(ObsEvent("executor.step.start", self.name,
                                              {"step_id": step.id, "description": step.description}))

        if not step.tool:
            return StepResult(step_id=step.id, success=True, output=None)

        tool = self.context.tools.get(step.tool)
        if tool is None:
            return StepResult(step_id=step.id, success=False, output=None,
                              error=f"Tool '{step.tool}' not found")

        if self.context.events:
            self.context.events.emit(ObsEvent("executor.tool.call", self.name,
                                              {"tool": step.tool, "inputs": step.inputs}))

        try:
            output = tool(step.inputs or {})
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.result", self.name,
                                                  {"tool": step.tool, "output": output}))
            return StepResult(step_id=step.id, success=True, output=output)
        except Exception as e:
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.error", self.name,
                                                  {"tool": step.tool, "error": str(e)}))
            return StepResult(step_id=step.id, success=False, output=None, error=str(e))

    def _summarize_step(self, task: str, step: PlanStep, result: StepResult) -> str:
        if not self.context.model_config or not self.llm:
            return f"Step {step.id} {'failed' if result.error else 'succeeded'}: {result.error or result.output}"

        tool_output_text = "SUCCESS: " + str(result.output) if result.success else "ERROR: " + str(result.error)

        messages = [
            {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT.strip()},
            {"role": "user", "content": f"Task: {task}\nStep {step.id}: {step.description}\nTool: {step.tool}\nOutput: {tool_output_text}"},
        ]

        tokens_estimate = sum(len(m["content"].split()) for m in messages)
        if self.context.rate_limiter:
            self.context.rate_limiter.check(self.name, self.context.model_config.name, tokens_estimate)

        start = time.time()
        resp = self.llm.generate(messages, self.context.model_config)
        end = time.time()
        latency_ms = (end - start) * 1000

        if self.context.events:
            self.context.events.emit(ObsEvent("llm.latency", self.name,
                                              {"model": self.context.model_config.name, "latency_ms": latency_ms}))
            self.context.events.emit(ObsEvent("llm.usage", self.name,
                                              {"model": self.context.model_config.name,
                                               "prompt_tokens": resp.prompt_tokens,
                                               "completion_tokens": resp.completion_tokens,
                                               "total_tokens": resp.total_tokens}))

        return resp.text

    def execute_plan(self, plan: Plan):
        messages = []
        for step in plan.steps:
            result = self._run_tool(step)
            summary = self._summarize_step(plan.task, step, result)
            content = f"Step {step.id}: {step.description}\nResult: {summary}"
            msg = make_message("agent", content,
                               metadata={"type": "execution_step",
                                         "step_id": step.id,
                                         "tool": step.tool,
                                         "success": result.success})
            self.context.short_term.append(msg)
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.step.complete", self.name,
                                                  {"step_id": step.id, "success": result.success}))
            messages.append(msg)
        return messages

    def step(self, incoming: Message) -> Message:
        data = json.loads(incoming.content)
        plan = Plan(
            task=data["task"],
            steps=[
                PlanStep(
                    id=s["id"],
                    description=s["description"],
                    tool=s.get("tool"),
                    inputs=s.get("inputs"),
                    notes=s.get("notes"),
                )
                for s in data["steps"]
            ],
        )
        self.context.short_term.append(incoming)
        msgs = self.execute_plan(plan)
        return msgs[-1] if msgs else make_message("agent", "No steps to execute", metadata={"type": "execution"})

    async def _run_tool_async(self, step: PlanStep) -> StepResult:
        if not step.tool:
            return StepResult(step_id=step.id, success=True, output=None)
        tool = self.context.tools.get(step.tool)
        if tool is None:
            return StepResult(step_id=step.id, success=False, output=None,
                              error=f"Tool '{step.tool}' not found")
        try:
            output = await tool.call_async(step.inputs or {})
            return StepResult(step_id=step.id, success=True, output=output)
        except Exception as e:
            return StepResult(step_id=step.id, success=False, output=None, error=str(e))

    async def _summarize_step_async(self, task: str, step: PlanStep, result: StepResult) -> str:
        if not self.context.model_config or not self.llm:
            return f"Step {step.id} {'failed' if result.error else 'succeeded'}: {result.error or result.output}"

        tool_output_text = "SUCCESS: " + str(result.output) if result.success else "ERROR: " + str(result.error)
        messages = [
            {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT.strip()},
            {"role": "user", "content": f"Task: {task}\nStep {step.id}: {step.description}\nTool: {step.tool}\nOutput: {tool_output_text}"},
        ]
        tokens_estimate = sum(len(m["content"].split()) for m in messages)
        if self.context.rate_limiter:
            self.context.rate_limiter.check(self.name, self.context.model_config.name, tokens_estimate)

        start = time.time()
        resp = await self.llm.generate_async(messages, self.context.model_config)
        end = time.time()
        latency_ms = (end - start) * 1000

        if self.context.events:
            self.context.events.emit(ObsEvent("llm.latency", self.name,
                                              {"model": self.context.model_config.name, "latency_ms": latency_ms}))
            self.context.events.emit(ObsEvent("llm.usage", self.name,
                                              {"model": self.context.model_config.name,
                                               "prompt_tokens": resp.prompt_tokens,
                                               "completion_tokens": resp.completion_tokens,
                                               "total_tokens": resp.total_tokens}))
        return resp.text

    async def execute_plan_async(self, plan: Plan):
        messages = []
        for step in plan.steps:
            result = await self._run_tool_async(step)
            summary = await self._summarize_step_async(plan.task, step, result)
            content = f"Step {step.id}: {step.description}\nResult: {summary}"
            msg = make_message("agent", content,
                               metadata={"type": "execution_step",
                                         "step_id": step.id,
                                         "tool": step.tool,
                                         "success": result.success})
            self.context.short_term.append(msg)
            messages.append(msg)
        return messages

    async def step_async(self, incoming: Message) -> Message:
        data = json.loads(incoming.content)
        plan = Plan(
            task=data["task"],
            steps=[
                PlanStep(
                    id=s["id"],
                    description=s["description"],
                    tool=s.get("tool"),
                    inputs=s.get("inputs"),
                    notes=s.get("notes"),
                )
                for s in data["steps"]
            ],
        )
        self.context.short_term.append(incoming)
        msgs = await self.execute_plan_async(plan)
        from agent_sdk.core.messages import make_message as _mm
        return msgs[-1] if msgs else _mm("agent", "No steps to execute", metadata={"type": "execution"})
EOF

################################
# observability/
################################
mkdir -p agent_sdk/observability

cat << 'EOF' > agent_sdk/observability/__init__.py
EOF

cat << 'EOF' > agent_sdk/observability/events.py
from dataclasses import dataclass, field
from typing import Any, Dict
import time, uuid

@dataclass
class ObsEvent:
    event_type: str
    agent: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=lambda: time.time())
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
EOF

cat << 'EOF' > agent_sdk/observability/sinks.py
from abc import ABC, abstractmethod
from .events import ObsEvent
import json

class EventSink(ABC):
    @abstractmethod
    def emit(self, event: ObsEvent):
        ...

class ConsoleSink(EventSink):
    def emit(self, event: ObsEvent):
        print(f"[{event.event_type}] {event.agent} :: {event.data}")

class JSONLSink(EventSink):
    def __init__(self, path: str):
        self.path = path

    def emit(self, event: ObsEvent):
        with open(self.path, "a") as f:
            f.write(json.dumps(event.__dict__) + "\n")
EOF

cat << 'EOF' > agent_sdk/observability/bus.py
from typing import List
from .events import ObsEvent
from .sinks import EventSink

class EventBus:
    def __init__(self, sinks: List[EventSink] | None = None):
        self.sinks = sinks or []

    def add_sink(self, sink: EventSink):
        self.sinks.append(sink)

    def emit(self, event: ObsEvent):
        for s in self.sinks:
            s.emit(event)
EOF

################################
# plugins/
################################
mkdir -p agent_sdk/plugins

cat << 'EOF' > agent_sdk/plugins/__init__.py
EOF

cat << 'EOF' > agent_sdk/plugins/loader.py
from importlib.metadata import entry_points
from agent_sdk.core.tools import GLOBAL_TOOL_REGISTRY
from agent_sdk.core.agent import Agent
from agent_sdk.llm.base import LLMClient

class PluginLoader:
    def __init__(self):
        self.tools = {}
        self.agents = {}
        self.llms = {}

    def load(self):
        eps = entry_points()

        for ep in eps.get("agent_sdk.tools", []):
            func = ep.load()
            func(GLOBAL_TOOL_REGISTRY)
            self.tools[ep.name] = func

        for ep in eps.get("agent_sdk.agents", []):
            cls = ep.load()
            if issubclass(cls, Agent):
                self.agents[ep.name] = cls

        for ep in eps.get("agent_sdk.llm", []):
            cls = ep.load()
            if issubclass(cls, LLMClient):
                self.llms[ep.name] = cls
EOF

################################
# cli/
################################
mkdir -p agent_sdk/cli

cat << 'EOF' > agent_sdk/cli/__init__.py
EOF

cat << 'EOF' > agent_sdk/cli/commands.py
import asyncio
import typer
import yaml

from agent_sdk.config.loader import load_config
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.core.tools import GLOBAL_TOOL_REGISTRY
from agent_sdk.plugins.loader import PluginLoader

run_cmd = typer.Typer(help="Run tasks using the agent runtime")
tools_cmd = typer.Typer(help="Inspect tools")
agents_cmd = typer.Typer(help="Inspect agents")
init_cmd = typer.Typer(help="Project scaffolding")
serve_cmd = typer.Typer(help="Serve agents over HTTP")

@run_cmd.command("task")
def run_task(task: str, config: str = "config.yaml"):
    loader = PluginLoader()
    loader.load()
    planner, executor = load_config(config, MockLLMClient())
    runtime = PlannerExecutorRuntime(planner, executor)
    msgs = asyncio.run(runtime.run_async(task))
    for m in msgs:
        typer.echo(f"{m.role.upper()}: {m.content}")

@run_cmd.command("file")
def run_file(file: str, config: str = "config.yaml"):
    with open(file, "r") as f:
        data = yaml.safe_load(f)
    task = data["task"]
    loader = PluginLoader()
    loader.load()
    planner, executor = load_config(config, MockLLMClient())
    runtime = PlannerExecutorRuntime(planner, executor)
    msgs = asyncio.run(runtime.run_async(task))
    for m in msgs:
        typer.echo(f"{m.role.upper()}: {m.content}")

@tools_cmd.command("list")
def list_tools():
    for name, tool in GLOBAL_TOOL_REGISTRY.tools.items():
        typer.echo(f"- {name}: {tool.description}")

@agents_cmd.command("list")
def list_agents(config: str = "config.yaml"):
    with open(config, "r") as f:
        cfg = yaml.safe_load(f)
    for name in cfg.get("agents", {}).keys():
        typer.echo(f"- {name}")

@init_cmd.command("project")
def init_project(name: str = "agent-app"):
    import os, textwrap
    os.makedirs(name, exist_ok=True)
    with open(os.path.join(name, "config.yaml"), "w") as f:
        f.write(textwrap.dedent("""
        models:
          planner:
            name: planner-gpt4
            provider: openai
            model_id: gpt-4o
            temperature: 0.1
            max_tokens: 2048

          executor:
            name: executor-mini
            provider: openai
            model_id: gpt-4o-mini
            temperature: 0.3
            max_tokens: 1024

        rate_limits: []
        agents:
          planner:
            model: planner
          executor:
            model: executor
        """).strip() + "\n")

    with open(os.path.join(name, "tools.py"), "w") as f:
        f.write(textwrap.dedent("""
        from agent_sdk import tool

        @tool("echo", "Echo back input")
        def echo(args):
            return args["text"]
        """).strip() + "\n")

    typer.echo(f"Initialized agent project in ./{name}")

@serve_cmd.command("http")
def serve_http(config: str = "config.yaml", host: str = "0.0.0.0", port: int = 9000):
    import uvicorn
    from agent_sdk.server.app import create_app
    loader = PluginLoader()
    loader.load()
    app = create_app(config)
    uvicorn.run(app, host=host, port=port)
EOF

cat << 'EOF' > agent_sdk/cli/main.py
import typer
from agent_sdk.cli.commands import run_cmd, tools_cmd, agents_cmd, init_cmd, serve_cmd

app = typer.Typer(help="Agent SDK CLI")
app.add_typer(run_cmd, name="run")
app.add_typer(tools_cmd, name="tools")
app.add_typer(agents_cmd, name="agents")
app.add_typer(init_cmd, name="init")
app.add_typer(serve_cmd, name="serve")

def main():
    app()
EOF

################################
# server/
################################
mkdir -p agent_sdk/server

cat << 'EOF' > agent_sdk/server/__init__.py
EOF

cat << 'EOF' > agent_sdk/server/app.py
from fastapi import FastAPI
from pydantic import BaseModel
from agent_sdk.config.loader import load_config
from agent_sdk.core.runtime import PlannerExecutorRuntime
from agent_sdk.llm.mock import MockLLMClient
from agent_sdk.plugins.loader import PluginLoader

class TaskRequest(BaseModel):
    task: str

def create_app(config_path: str = "config.yaml"):
    loader = PluginLoader()
    loader.load()
    planner, executor = load_config(config_path, MockLLMClient())
    runtime = PlannerExecutorRuntime(planner, executor)

    app = FastAPI()

    @app.post("/run")
    async def run_task(req: TaskRequest):
        msgs = await runtime.run_async(req.task)
        return {"messages": [m.__dict__ for m in msgs]}

    return app
EOF

################################
# dashboard backend
################################
mkdir -p agent_sdk/dashboard

cat << 'EOF' > agent_sdk/dashboard/__init__.py
EOF

cat << 'EOF' > agent_sdk/dashboard/server.py
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
import asyncio
import json

class DashboardServer:
    def __init__(self, event_bus):
        self.app = FastAPI()
        self.event_bus = event_bus
        self.queue: asyncio.Queue = asyncio.Queue()

        @self.app.get("/")
        async def index():
            return HTMLResponse(self._html())

        @self.app.get("/events")
        async def events():
            async def event_stream():
                while True:
                    event = await self.queue.get()
                    yield f"data: {json.dumps(event)}\\n\\n"
            return StreamingResponse(event_stream(), media_type="text/event-stream")

        original_emit = event_bus.emit

        def patched_emit(event):
            original_emit(event)
            try:
                asyncio.get_running_loop()
                asyncio.create_task(self.queue.put(event.__dict__))
            except RuntimeError:
                # no running loop; ignore live streaming
                pass

        event_bus.emit = patched_emit

    def _html(self):
        return """
        <html>
        <body>
            <h1>Agent Dashboard</h1>
            <pre id="log"></pre>
            <script>
                const log = document.getElementById("log");
                const evtSource = new EventSource("/events");
                evtSource.onmessage = function(e) {
                    const data = JSON.parse(e.data);
                    log.textContent += JSON.stringify(data, null, 2) + "\\n";
                };
            </script>
        </body>
        </html>
        """

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        import uvicorn
        uvicorn.run(self.app, host=host, port=port)
EOF

################################
# pyproject + README
################################
cat << 'EOF' > pyproject.toml
[project]
name = "agent-sdk"
version = "0.1.0"
description = "A modular agent framework with planning, execution, tools, rate limiting, observability, plugins, CLI, server, and dashboard."
authors = [{ name="Hongwei" }]
readme = "README.md"
requires-python = ">=3.9"
dependencies = [
    "pyyaml>=6.0",
    "typer>=0.12.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
]

[project.scripts]
agent-sdk = "agent_sdk.cli.main:main"

[project.entry-points."agent_sdk.tools"]
# plugin_name = "module:function"

[project.entry-points."agent_sdk.agents"]
# plugin_name = "module:AgentClass"

[project.entry-points."agent_sdk.llm"]
# plugin_name = "module:LLMClientClass"
EOF

cat << 'EOF' > README.md
# Agent SDK

A modular, extensible agent framework featuring:

- Planner + Executor architecture
- Tooling system with decorators and registry
- LLM abstraction layer
- Rate limiting (per model/agent, tokens + calls)
- Observability (events, sinks, dashboard backend)
- Plugin system (tools, agents, LLM providers via entry points)
- Async support (LLM, tools, runtime)
- CLI (`agent-sdk`)
- Local agent server (FastAPI)
- Dashboard (FastAPI + SSE)

## Quickstart

```bash
pip install -e .
agent-sdk init project my-app
cd my-app
python -c "from tools import echo; print('ok')"

EOF