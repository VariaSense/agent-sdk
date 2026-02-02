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
