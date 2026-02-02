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
