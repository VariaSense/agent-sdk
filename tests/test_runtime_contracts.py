from agent_sdk.contracts.runtime import CONTRACT_VERSION, AgentDefinition, ExecutionMetadata, RunEvent, RunRequest, RunResult


def test_runtime_contracts_default_to_v1():
    assert CONTRACT_VERSION == "v1"
    assert AgentDefinition(name="demo").contract_version == "v1"
    assert ExecutionMetadata().contract_version == "v1"
    assert RunRequest(agent=AgentDefinition(name="demo"), prompt="hi").contract_version == "v1"
    assert RunEvent(stream="lifecycle", event="started").contract_version == "v1"
    assert RunResult(status="completed", response="ok").contract_version == "v1"
