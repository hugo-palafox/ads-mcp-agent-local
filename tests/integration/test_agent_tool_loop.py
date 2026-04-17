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
        self.calls = []

    def complete(self, messages, tools):
        self.calls.append((messages, tools))
        return self.responses.pop(0)


def test_multi_step_tool_loop() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(content=None, tool_calls=[ModelToolCall(id="1", name="list_memory_tags", arguments={})], raw={}),
            ModelResponse(content=None, tool_calls=[ModelToolCall(id="2", name="read_memory", arguments={})], raw={}),
            ModelResponse(content="Machine is running.", tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "list_memory_tags": [{"name": "Globals.bRun"}],
                "read_memory": {"Globals.bRun": True},
            }
        )
    )  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="Summarize the machine")
    assert result.answer == "Machine is running."
    assert [item.tool_name for item in result.tool_trace] == ["list_memory_tags", "read_memory"]
