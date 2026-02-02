"""Tests for multi-agent orchestration."""

import pytest
from agent_sdk.agents.orchestrator import (
    MessageType,
    AgentRole,
    ConsensusAlgorithm,
    Message,
    SharedContext,
    AgentState,
    MessageRouter,
    ConsensusVote,
    MultiAgentOrchestrator,
    create_multi_agent_system,
)


class TestMessage:
    """Test Message functionality."""

    def test_create_message(self):
        """Test creating a message."""
        message = Message(
            message_id="msg1",
            sender_id="agent1",
            recipients=["agent2"],
            message_type=MessageType.REQUEST,
            content={"task": "solve"},
        )
        assert message.sender_id == "agent1"
        assert "agent2" in message.recipients

    def test_create_request_message(self):
        """Test creating request message."""
        message = Message.create_request(
            "agent1", ["agent2"], {"task": "analyze"}
        )
        assert message.message_type == MessageType.REQUEST
        assert message.sender_id == "agent1"

    def test_create_response_message(self):
        """Test creating response message."""
        message = Message.create_response(
            "agent2", "agent1", {"result": "done"}, priority=5
        )
        assert message.message_type == MessageType.RESPONSE
        assert message.recipients == ["agent1"]
        assert message.priority == 5

    def test_message_to_dict(self):
        """Test converting message to dict."""
        message = Message.create_request(
            "agent1", ["agent2"], {"data": "info"}
        )
        msg_dict = message.to_dict()
        assert msg_dict["sender_id"] == "agent1"
        assert msg_dict["message_type"] == "request"


class TestSharedContext:
    """Test SharedContext functionality."""

    def test_create_context(self):
        """Test creating shared context."""
        context = SharedContext(
            context_id="ctx1", global_goal="solve_problem"
        )
        assert context.context_id == "ctx1"
        assert context.global_goal == "solve_problem"

    def test_set_and_get_data(self):
        """Test setting and getting shared data."""
        context = SharedContext(context_id="ctx1")
        context.set_data("knowledge", "facts", "agent1")
        value = context.get_data("knowledge", "agent1")
        assert value == "facts"

    def test_context_to_dict(self):
        """Test converting context to dict."""
        context = SharedContext(context_id="ctx1", global_goal="goal")
        context.set_data("key", "value", "agent1")
        ctx_dict = context.to_dict()
        assert ctx_dict["context_id"] == "ctx1"
        assert ctx_dict["global_goal"] == "goal"


class TestAgentState:
    """Test AgentState functionality."""

    def test_create_agent_state(self):
        """Test creating agent state."""
        state = AgentState(
            agent_id="agent1",
            name="Agent One",
            role=AgentRole.WORKER,
        )
        assert state.agent_id == "agent1"
        assert state.role == AgentRole.WORKER
        assert state.status == "idle"

    def test_agent_state_to_dict(self):
        """Test converting agent state to dict."""
        state = AgentState(
            agent_id="agent1", name="Agent", role=AgentRole.COORDINATOR
        )
        state_dict = state.to_dict()
        assert state_dict["agent_id"] == "agent1"
        assert state_dict["role"] == "coordinator"


class TestMessageRouter:
    """Test MessageRouter functionality."""

    def test_create_router(self):
        """Test creating message router."""
        router = MessageRouter()
        assert len(router.message_queues) == 0

    def test_register_agent(self):
        """Test registering agent with router."""
        router = MessageRouter()
        router.register_agent("agent1")
        assert "agent1" in router.message_queues

    def test_send_message(self):
        """Test sending message."""
        router = MessageRouter()
        router.register_agent("agent1")
        router.register_agent("agent2")

        message = Message.create_request("agent1", ["agent2"], {"task": "go"})
        router.send_message(message)

        assert len(router.message_history) == 1
        assert len(router.message_queues["agent2"]) == 1

    def test_get_messages(self):
        """Test retrieving messages for agent."""
        router = MessageRouter()
        router.register_agent("agent1")

        message = Message.create_request("sender", ["agent1"], {"data": "info"})
        router.send_message(message)

        messages = router.get_messages("agent1")
        assert len(messages) == 1
        assert messages[0].sender_id == "sender"

    def test_broadcast_message(self):
        """Test broadcasting message."""
        router = MessageRouter()
        router.register_agent("agent1")
        router.register_agent("agent2")
        router.register_agent("agent3")

        router.broadcast_message(
            "sender", ["agent1", "agent2", "agent3"], {"alert": "info"}
        )

        assert len(router.message_history) == 1


class TestConsensusVote:
    """Test ConsensusVote functionality."""

    def test_create_vote(self):
        """Test creating consensus vote."""
        vote = ConsensusVote("proposal1", ConsensusAlgorithm.MAJORITY)
        assert vote.proposal_id == "proposal1"
        assert vote.algorithm == ConsensusAlgorithm.MAJORITY

    def test_cast_votes_majority(self):
        """Test majority consensus."""
        vote = ConsensusVote("prop1", ConsensusAlgorithm.MAJORITY)
        vote.cast_vote("agent1", True)
        vote.cast_vote("agent2", True)
        vote.cast_vote("agent3", False)

        result = vote.get_result()
        assert result is True

    def test_unanimous_consensus(self):
        """Test unanimous consensus."""
        vote = ConsensusVote("prop1", ConsensusAlgorithm.UNANIMOUS)
        vote.cast_vote("agent1", True)
        vote.cast_vote("agent2", True)
        vote.cast_vote("agent3", False)

        result = vote.get_result()
        assert result is False

    def test_vote_to_dict(self):
        """Test converting vote to dict."""
        vote = ConsensusVote("prop1", ConsensusAlgorithm.MAJORITY)
        vote.cast_vote("agent1", True)
        vote.cast_vote("agent2", False)

        vote_dict = vote.to_dict()
        assert vote_dict["total_votes"] == 2
        assert vote_dict["yes_votes"] == 1


class TestMultiAgentOrchestrator:
    """Test MultiAgentOrchestrator functionality."""

    def test_create_orchestrator(self):
        """Test creating orchestrator."""
        orchestrator = create_multi_agent_system("system1")
        assert orchestrator.system_id == "system1"

    def test_register_agents(self):
        """Test registering multiple agents."""
        orchestrator = create_multi_agent_system()
        orchestrator.register_agent("agent1", "Worker 1", AgentRole.WORKER)
        orchestrator.register_agent("agent2", "Worker 2", AgentRole.WORKER)
        orchestrator.register_agent(
            "coordinator", "Coordinator", AgentRole.COORDINATOR
        )

        assert len(orchestrator.agents) == 3

    def test_create_shared_context(self):
        """Test creating shared context."""
        orchestrator = create_multi_agent_system()
        context = orchestrator.create_shared_context("Solve the problem")
        assert context is not None
        assert context.global_goal == "Solve the problem"

    def test_send_message(self):
        """Test sending message between agents."""
        orchestrator = create_multi_agent_system()
        orchestrator.register_agent("agent1", "A1", AgentRole.WORKER)
        orchestrator.register_agent("agent2", "A2", AgentRole.WORKER)

        orchestrator.send_message(
            "agent1",
            ["agent2"],
            MessageType.REQUEST,
            {"task": "analyze"},
        )

        messages = orchestrator.router.get_messages("agent2")
        assert len(messages) == 1

    def test_propose_consensus(self):
        """Test proposing consensus."""
        orchestrator = create_multi_agent_system()
        orchestrator.register_agent("agent1", "A1", AgentRole.WORKER)
        orchestrator.register_agent("agent2", "A2", AgentRole.WORKER)

        vote = orchestrator.propose_consensus(
            "decision1",
            ConsensusAlgorithm.MAJORITY,
            ["agent1", "agent2"],
        )

        assert "decision1" in orchestrator.active_consensus
        assert vote.algorithm == ConsensusAlgorithm.MAJORITY

    def test_agent_status(self):
        """Test getting agent status."""
        orchestrator = create_multi_agent_system()
        orchestrator.register_agent("agent1", "A1", AgentRole.WORKER)
        orchestrator.register_agent("agent2", "A2", AgentRole.COORDINATOR)

        status = orchestrator.get_agent_status()
        assert status["total_agents"] == 2

    def test_system_status(self):
        """Test getting system status."""
        orchestrator = create_multi_agent_system()
        orchestrator.register_agent("agent1", "A1", AgentRole.WORKER)

        sys_status = orchestrator.get_system_status()
        assert sys_status["total_agents"] == 1
        assert sys_status["idle_agents"] == 1

    def test_orchestrator_to_dict(self):
        """Test converting orchestrator to dict."""
        orchestrator = create_multi_agent_system("system1")
        orchestrator.register_agent("agent1", "A1", AgentRole.WORKER)

        orch_dict = orchestrator.to_dict()
        assert orch_dict["system_id"] == "system1"
        assert orch_dict["agent_count"] == 1


class TestMultiAgentIntegration:
    """Integration tests for multi-agent system."""

    def test_complete_multi_agent_workflow(self):
        """Test complete multi-agent workflow."""
        # Create system
        orchestrator = create_multi_agent_system("problem_solver")

        # Register agents
        orchestrator.register_agent("analyzer", "Data Analyzer", AgentRole.WORKER)
        orchestrator.register_agent("processor", "Data Processor", AgentRole.WORKER)
        orchestrator.register_agent("coordinator", "Coordinator", AgentRole.COORDINATOR)

        # Create shared context
        context = orchestrator.create_shared_context("Analyze data")

        # Send messages
        orchestrator.send_message(
            "coordinator",
            ["analyzer"],
            MessageType.REQUEST,
            {"data": "sample"},
        )

        # Verify system
        system_status = orchestrator.get_system_status()
        assert system_status["total_agents"] == 3
        assert system_status["working_agents"] == 0

    def test_consensus_voting_workflow(self):
        """Test consensus voting."""
        orchestrator = create_multi_agent_system()

        # Register agents
        agents = ["agent1", "agent2", "agent3"]
        for agent_id in agents:
            orchestrator.register_agent(agent_id, f"Agent {agent_id}", AgentRole.WORKER)

        # Propose decision
        vote = orchestrator.propose_consensus(
            "decision", ConsensusAlgorithm.MAJORITY, agents
        )

        # Cast votes
        vote.cast_vote("agent1", True)
        vote.cast_vote("agent2", True)
        vote.cast_vote("agent3", False)

        result = vote.get_result()
        assert result is True

    def test_message_routing(self):
        """Test message routing between multiple agents."""
        orchestrator = create_multi_agent_system()

        # Register agents
        for i in range(3):
            orchestrator.register_agent(f"agent{i}", f"Agent {i}", AgentRole.WORKER)

        # Send messages in sequence
        orchestrator.send_message(
            "agent0", ["agent1"], MessageType.REQUEST, {"data": "A"}
        )
        orchestrator.send_message(
            "agent1", ["agent2"], MessageType.REQUEST, {"data": "B"}
        )

        # Verify routing
        messages_agent1 = orchestrator.router.get_messages("agent1")
        messages_agent2 = orchestrator.router.get_messages("agent2")

        assert len(messages_agent1) == 1
        assert len(messages_agent2) == 1
