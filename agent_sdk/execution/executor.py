import json
import time
import logging
from agent_sdk.core.agent import Agent
from agent_sdk.core.messages import Message, make_message
from agent_sdk.observability.events import ObsEvent
from agent_sdk.planning.plan_schema import Plan, PlanStep
from agent_sdk.exceptions import ToolError, LLMError
from agent_sdk.core.retry import retry_with_backoff
from .step_result import StepResult

logger = logging.getLogger(__name__)

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
        """Execute a tool with comprehensive error handling"""
        if self.context.events:
            self.context.events.emit(ObsEvent("executor.step.start", self.name,
                                              {"step_id": step.id, "description": step.description}))

        if not step.tool:
            return StepResult(step_id=step.id, success=True, output=None)

        tool = self.context.tools.get(step.tool)
        if tool is None:
            error_msg = f"Tool '{step.tool}' not found"
            logger.error(error_msg)
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.not_found", self.name,
                                                  {"tool": step.tool}))
                self.context.events.emit(ObsEvent("tool.latency", self.name,
                                                  {"tool": step.tool, "latency_ms": 0.0, "success": False}))
            return StepResult(step_id=step.id, success=False, output=None,
                              error=error_msg)

        if self.context.events:
            self.context.events.emit(ObsEvent("executor.tool.call", self.name,
                                              {"tool": step.tool, "inputs": step.inputs}))

        start = time.time()
        success = False
        try:
            # Validate inputs
            if step.inputs is None:
                step.inputs = {}
            if not isinstance(step.inputs, dict):
                raise ToolError(f"Tool inputs must be a dictionary, got {type(step.inputs)}")
            
            output = tool(step.inputs)
            success = True
            
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.result", self.name,
                                                  {"tool": step.tool, "output": str(output)[:500]}))
            
            logger.debug(f"Tool '{step.tool}' executed successfully")
            return StepResult(step_id=step.id, success=True, output=output)
            
        except ToolError as e:
            logger.error(f"Tool error in '{step.tool}': {str(e)}")
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.error", self.name,
                                                  {"tool": step.tool, "error": str(e), "error_type": "ToolError"}))
            return StepResult(step_id=step.id, success=False, output=None, error=str(e))
            
        except Exception as e:
            error_msg = f"Unexpected error in tool '{step.tool}': {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.error", self.name,
                                                  {"tool": step.tool, "error": str(e), "error_type": type(e).__name__}))
            return StepResult(step_id=step.id, success=False, output=None, error=str(e))
        finally:
            latency_ms = (time.time() - start) * 1000
            if self.context.events:
                self.context.events.emit(ObsEvent("tool.latency", self.name,
                                                  {"tool": step.tool, "latency_ms": latency_ms,
                                                   "success": success}))

    def _summarize_step(self, task: str, step: PlanStep, result: StepResult) -> str:
        """Summarize step result with retry logic"""
        if not self.context.model_config or not self.llm:
            status = "succeeded" if result.success else "failed"
            detail = result.error if result.error else result.output
            return f"Step {step.id} {status}: {detail}"

        tool_output_text = "SUCCESS: " + str(result.output) if result.success else "ERROR: " + str(result.error)

        messages = [
            {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT.strip()},
            {"role": "user", "content": f"Task: {task}\nStep {step.id}: {step.description}\nTool: {step.tool}\nOutput: {tool_output_text}"},
        ]

        tokens_estimate = sum(len(m["content"].split()) for m in messages)
        if self.context.rate_limiter:
            self.context.rate_limiter.check(self.name, self.context.model_config.name, tokens_estimate)

        try:
            from agent_sdk.core.retry import sync_retry_with_backoff
            start = time.time()
            resp = sync_retry_with_backoff(
                lambda: self.llm.generate(messages, self.context.model_config),
                max_retries=3
            )
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
            
        except LLMError as e:
            logger.error(f"LLM error in step summarization: {str(e)}")
            if self.context.events:
                self.context.events.emit(ObsEvent("llm.error", self.name,
                                                  {"error": str(e), "step_id": step.id}))
            return f"Failed to summarize step: {str(e)}"
            
        except Exception as e:
            error_msg = f"Unexpected error in step summarization: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.error", self.name,
                                                  {"error": str(e), "error_type": type(e).__name__}))
            return f"Error during summarization: {str(e)}"

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
            self.context.apply_run_metadata(msg)
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
        """Execute a tool asynchronously with comprehensive error handling"""
        if self.context.events:
            self.context.events.emit(ObsEvent("executor.step.start", self.name,
                                              {"step_id": step.id, "description": step.description}))

        if not step.tool:
            return StepResult(step_id=step.id, success=True, output=None)
        
        tool = self.context.tools.get(step.tool)
        if tool is None:
            error_msg = f"Tool '{step.tool}' not found"
            logger.error(error_msg)
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.not_found", self.name,
                                                  {"tool": step.tool}))
                self.context.events.emit(ObsEvent("tool.latency", self.name,
                                                  {"tool": step.tool, "latency_ms": 0.0, "success": False}))
            return StepResult(step_id=step.id, success=False, output=None, error=error_msg)
        
        if self.context.events:
            self.context.events.emit(ObsEvent("executor.tool.call", self.name,
                                              {"tool": step.tool, "inputs": step.inputs}))
        
        start = time.time()
        success = False
        try:
            # Validate inputs
            if step.inputs is None:
                step.inputs = {}
            if not isinstance(step.inputs, dict):
                raise ToolError(f"Tool inputs must be a dictionary, got {type(step.inputs)}")
            
            observability = self.context.config.get("observability")
            if observability:
                with observability.trace_tool_call(step.tool, step.inputs):
                    output = await tool.call_async(step.inputs)
            else:
                output = await tool.call_async(step.inputs)
            success = True
            
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.result", self.name,
                                                  {"tool": step.tool, "output": str(output)[:500]}))
            
            logger.debug(f"Tool '{step.tool}' executed successfully")
            return StepResult(step_id=step.id, success=True, output=output)
            
        except ToolError as e:
            logger.error(f"Tool error in '{step.tool}': {str(e)}")
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.error", self.name,
                                                  {"tool": step.tool, "error": str(e), "error_type": "ToolError"}))
            return StepResult(step_id=step.id, success=False, output=None, error=str(e))
            
        except Exception as e:
            error_msg = f"Unexpected error in tool '{step.tool}': {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.tool.error", self.name,
                                                  {"tool": step.tool, "error": str(e), "error_type": type(e).__name__}))
            return StepResult(step_id=step.id, success=False, output=None, error=str(e))
        finally:
            latency_ms = (time.time() - start) * 1000
            if self.context.events:
                self.context.events.emit(ObsEvent("tool.latency", self.name,
                                                  {"tool": step.tool, "latency_ms": latency_ms,
                                                   "success": success}))

    async def _summarize_step_async(self, task: str, step: PlanStep, result: StepResult) -> str:
        """Summarize step result asynchronously with retry logic"""
        if not self.context.model_config or not self.llm:
            status = "succeeded" if result.success else "failed"
            detail = result.error if result.error else result.output
            return f"Step {step.id} {status}: {detail}"

        tool_output_text = "SUCCESS: " + str(result.output) if result.success else "ERROR: " + str(result.error)
        messages = [
            {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT.strip()},
            {"role": "user", "content": f"Task: {task}\nStep {step.id}: {step.description}\nTool: {step.tool}\nOutput: {tool_output_text}"},
        ]
        
        tokens_estimate = sum(len(m["content"].split()) for m in messages)
        if self.context.rate_limiter:
            self.context.rate_limiter.check(self.name, self.context.model_config.name, tokens_estimate)

        try:
            start = time.time()
            observability = self.context.config.get("observability")
            if observability:
                with observability.trace_model_call(self.context.model_config.name, self.context.model_config.provider):
                    resp = await retry_with_backoff(
                        self.llm.generate_async,
                        max_retries=3,
                        messages=messages,
                        model_config=self.context.model_config,
                    )
            else:
                resp = await retry_with_backoff(
                    self.llm.generate_async,
                    max_retries=3,
                    messages=messages,
                    model_config=self.context.model_config,
                )
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
            
        except LLMError as e:
            logger.error(f"LLM error in step summarization: {str(e)}")
            if self.context.events:
                self.context.events.emit(ObsEvent("llm.error", self.name,
                                                  {"error": str(e), "step_id": step.id}))
            return f"Failed to summarize step: {str(e)}"
            
        except Exception as e:
            error_msg = f"Unexpected error in step summarization: {type(e).__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.context.events:
                self.context.events.emit(ObsEvent("executor.error", self.name,
                                                  {"error": str(e), "error_type": type(e).__name__}))
            return f"Error during summarization: {str(e)}"

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
