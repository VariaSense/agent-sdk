"""Tests for hierarchical orchestration cancellation."""

from agent_sdk.agents.orchestrator import MultiAgentOrchestrator, AgentRole, TaskStatus


def test_cancel_propagates_to_children():
    orchestrator = MultiAgentOrchestrator()
    orchestrator.register_agent("agent1", "Agent 1", AgentRole.WORKER)
    orchestrator.create_task("parent", ["agent1"])
    orchestrator.create_task("child", ["agent1"], parent_id="parent")

    orchestrator.cancel_task("parent", reason="test")
    assert orchestrator.tasks["parent"].status == TaskStatus.CANCELED
    assert orchestrator.tasks["child"].status == TaskStatus.CANCELED
