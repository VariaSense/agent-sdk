import json
import time
import logging
from typing import List, Dict
from agent_sdk.core.agent import Agent
from agent_sdk.core.messages import Message, make_message
from agent_sdk.observability.events import ObsEvent
from agent_sdk.planning.plan_schema import Plan, PlanStep
from agent_sdk.exceptions import LLMError
from agent_sdk.core.retry import retry_with_backoff

logger = logging.getLogger(__name__)

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

        try:
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
                if not isinstance(data, dict) or "steps" not in data:
                    raise ValueError("Invalid plan format: missing 'steps' key")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM output as JSON: {e}. Raw output: {raw}")
                # Create a fallback plan with the raw output as description
                plan = Plan(task=task, steps=[PlanStep(id=1, description=raw)])
            except ValueError as e:
                logger.warning(f"Invalid plan format: {e}")
                plan = Plan(task=task, steps=[PlanStep(id=1, description=f"Plan: {raw}")])
            else:
                plan = Plan(
                    task=data.get("task", task),
                    steps=[
                        PlanStep(
                            id=s.get("id", i + 1),
                            description=s.get("description", ""),
                            tool=s.get("tool"),
                            inputs=s.get("inputs"),
                            notes=s.get("notes"),
                        )
                        for i, s in enumerate(data.get("steps", []))
                    ],
                )

            if self.context.events:
                self.context.events.emit(ObsEvent("planner.complete", self.name, {"steps": len(plan.steps)}))

            return plan

        except Exception as e:
            logger.error(f"Planning failed: {str(e)}", exc_info=True)
            if self.context.events:
                self.context.events.emit(ObsEvent("planner.error", self.name, {"error": str(e)}))
            # Return fallback plan
            return Plan(task=task, steps=[PlanStep(id=1, description=f"Error during planning: {str(e)}")])

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
        self.context.apply_run_metadata(reply)
        self.context.short_term.append(incoming)
        self.context.short_term.append(reply)
        return reply

    async def plan_async(self, task: str) -> Plan:
        """Async version of plan with retry logic"""
        if self.context.events:
            self.context.events.emit(ObsEvent("planner.start", self.name, {"task": task}))

        try:
            prompt = self._build_prompt(task)
            tokens_estimate = sum(len(m["content"].split()) for m in prompt)

            if self.context.rate_limiter and self.context.model_config:
                self.context.rate_limiter.check(self.name, self.context.model_config.name, tokens_estimate)

            # Retry LLM call with backoff
            start = time.time()
            resp = await retry_with_backoff(
                self.llm.generate_async,
                max_retries=3,
                base_delay=1.0,
                prompt=prompt,
                model_config=self.context.model_config
            )
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
            try:
                data = json.loads(raw)
                if not isinstance(data, dict) or "steps" not in data:
                    raise ValueError("Invalid plan format")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse plan: {e}")
                return Plan(task=task, steps=[PlanStep(id=1, description=raw)])

            plan = Plan(
                task=data.get("task", task),
                steps=[
                    PlanStep(
                        id=s.get("id", i + 1),
                        description=s.get("description", ""),
                        tool=s.get("tool"),
                        inputs=s.get("inputs"),
                        notes=s.get("notes"),
                    )
                    for i, s in enumerate(data.get("steps", []))
                ],
            )

            if self.context.events:
                self.context.events.emit(ObsEvent("planner.complete", self.name, {"steps": len(plan.steps)}))

            return plan

        except Exception as e:
            logger.error(f"Async planning failed: {str(e)}", exc_info=True)
            if self.context.events:
                self.context.events.emit(ObsEvent("planner.error", self.name, {"error": str(e)}))
            return Plan(task=task, steps=[PlanStep(id=1, description=f"Error: {str(e)}")])

    async def step_async(self, incoming: Message) -> Message:
        plan = await self.plan_async(incoming.content)
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
