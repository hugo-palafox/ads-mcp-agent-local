from __future__ import annotations

from agent.orchestrator import AgentOrchestrator
from agent.tool_executor import ToolExecutor
from agent.tool_registry import ToolRegistry
from llm.schemas import ModelResponse, ModelToolCall
from mcp_bridge.ads_tools import AdsToolBridge
from tests.fixtures.fake_mcp_client import FakeMcpClient
from tests.fixtures.sample_configs import sample_settings


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, messages, tools):
        return self.responses.pop(0)


def test_read_memory_flow() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(content=None, tool_calls=[ModelToolCall(id="1", name="read_memory", arguments={})], raw={}),
            ModelResponse(content="Machine summary grounded in memory.", tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(FakeMcpClient(responses={"read_memory": {"Globals.bRun": True, "Globals.bFault": False}}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="What is the machine state?")
    assert result.answer == "Machine summary grounded in memory."
    assert result.tool_trace[0].tool_name == "read_memory"
    assert result.tool_trace[0].output["Globals.bRun"] is True


def test_read_memory_flow_overrides_model_machine_id_with_runtime_machine_context() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(
                content=None,
                tool_calls=[ModelToolCall(id="1", name="read_memory", arguments={"machine_id": "M1"})],
                raw={},
            ),
            ModelResponse(content="Machine summary grounded in memory.", tool_calls=[], raw={}),
        ]
    )
    fake_client = FakeMcpClient(responses={"read_memory": {"Globals.bRun": True}})  # type: ignore[arg-type]
    bridge = AdsToolBridge(fake_client)
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))

    result = orchestrator.run(machine_id="Machine1", prompt="What is the machine state?")

    assert result.answer == "Machine summary grounded in memory."
    assert fake_client.calls[0] == ("read_memory", {"machine_id": "Machine1"})


def test_read_memory_flow_empty_final_content_has_clear_fallback() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(content=None, tool_calls=[ModelToolCall(id="1", name="read_memory", arguments={})], raw={}),
            ModelResponse(content=None, tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(FakeMcpClient(responses={"read_memory": {}}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="What is the machine state?")
    assert result.answer == "No memory values were returned for this machine. Configure memory tags in ads-mcp-server and try again."
    assert result.tool_trace[0].tool_name == "read_memory"
    assert result.tool_trace[0].output == {}


def test_list_memory_tags_empty_final_content_has_clear_fallback() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(content=None, tool_calls=[ModelToolCall(id="1", name="list_memory_tags", arguments={})], raw={}),
            ModelResponse(content=None, tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(FakeMcpClient(responses={"list_memory_tags": []}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="Help me set up a machine")
    assert result.answer == "No curated memory tags are configured for this machine. Use ads-mcp-server setup/discovery commands, then add memory tags."
    assert result.tool_trace[0].tool_name == "list_memory_tags"
    assert result.tool_trace[0].output == []
