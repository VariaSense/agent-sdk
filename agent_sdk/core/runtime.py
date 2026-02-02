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
