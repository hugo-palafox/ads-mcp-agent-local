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


def test_read_tag_flow() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(content=None, tool_calls=[ModelToolCall(id="1", name="read_tag", arguments={"tag_name": "Globals.bRun"})], raw={}),
            ModelResponse(content="Globals.bRun is true.", tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(FakeMcpClient(responses={"read_tag": {"tag_name": "Globals.bRun", "value": True}}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="Read Globals.bRun")
    assert result.answer == "Globals.bRun is true."
    assert result.tool_trace[0].arguments["machine_id"] == "M1"
