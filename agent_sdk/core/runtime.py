from typing import List, Optional
from .messages import Message, make_message
from agent_sdk.planning.planner import PlannerAgent
from agent_sdk.execution.executor import ExecutorAgent
from agent_sdk.observability.stream_envelope import new_run_id, new_session_id

class PlannerExecutorRuntime:
    def __init__(self, planner: PlannerAgent, executor: ExecutorAgent):
        self.planner = planner
        self.executor = executor

    def _prepare_run_context(
        self,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> None:
        resolved_session_id = session_id or self.planner.context.session_id or new_session_id()
        resolved_run_id = run_id or new_run_id()

        self.planner.context.set_run_context(resolved_session_id, resolved_run_id)
        self.executor.context.set_run_context(resolved_session_id, resolved_run_id)

    def run(
        self,
        task_text: str,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> List[Message]:
        self._prepare_run_context(session_id=session_id, run_id=run_id)
        task_msg = make_message("user", task_text)
        self.planner.context.apply_run_metadata(task_msg)
        observability = self.planner.context.config.get("observability")
        if observability:
            with observability.trace_agent_execution(self.planner.name, task_text):
                plan_msg = self.planner.step(task_msg)
            with observability.trace_agent_execution(self.executor.name, task_text):
                exec_msg = self.executor.step(plan_msg)
        else:
            plan_msg = self.planner.step(task_msg)
            exec_msg = self.executor.step(plan_msg)
        self.planner.context.apply_run_metadata(plan_msg)
        self.executor.context.apply_run_metadata(exec_msg)
        return [plan_msg, exec_msg]

    async def run_async(
        self,
        task_text: str,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> List[Message]:
        self._prepare_run_context(session_id=session_id, run_id=run_id)
        task_msg = make_message("user", task_text)
        self.planner.context.apply_run_metadata(task_msg)
        observability = self.planner.context.config.get("observability")
        if observability:
            with observability.trace_agent_execution(self.planner.name, task_text):
                plan_msg = await self.planner.step_async(task_msg)
            with observability.trace_agent_execution(self.executor.name, task_text):
                exec_msg = await self.executor.step_async(plan_msg)
        else:
            plan_msg = await self.planner.step_async(task_msg)
            exec_msg = await self.executor.step_async(plan_msg)
        self.planner.context.apply_run_metadata(plan_msg)
        self.executor.context.apply_run_metadata(exec_msg)
        return [plan_msg, exec_msg]
