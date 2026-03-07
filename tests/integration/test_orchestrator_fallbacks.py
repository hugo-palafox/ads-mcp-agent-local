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


def test_empty_final_after_read_memory_returns_deterministic_summary() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(content=None, tool_calls=[ModelToolCall(id="1", name="read_memory", arguments={})], raw={}),
            ModelResponse(content=None, tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "read_memory": {
                    "Globals.bRun": False,
                    "Globals.bFault": False,
                    "Globals.nMachineState": 3,
                    "Globals.nGood": 141,
                }
            }
        )
    )  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(
        sample_settings(),
        llm,
        ToolRegistry(),
        ToolExecutor(ToolRegistry(), bridge),
        write_confirmer=lambda pending: True,
    )
    result = orchestrator.run(machine_id="M1", prompt="What is the machine state?")
    assert "Model returned no final text." in result.answer
    assert "Globals.nMachineState=3" in result.answer
    assert "Globals.bRun=False" in result.answer


def test_write_without_value_returns_clear_fallback() -> None:
    llm = FakeLLMClient([ModelResponse(content=None, tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="Set Globals.bStopButton")
    assert result.answer == "Write request is missing a target value. Example: Set Globals.bStopButton to true."


def test_start_intent_adds_runtime_hint_to_user_message() -> None:
    llm = FakeLLMClient([ModelResponse(content="ok", tool_calls=[], raw={})])
    bridge = AdsToolBridge(FakeMcpClient(responses={}))  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    orchestrator.run(machine_id="M1", prompt="Start Machine1")

    first_call_messages = llm.calls[0][0]
    user_message = next(msg for msg in first_call_messages if msg["role"] == "user")
    assert "Intent hint: start command likely means request_tag_write" in user_message["content"]


def test_stop_intent_without_model_output_executes_direct_write_flow() -> None:
    llm = FakeLLMClient([ModelResponse(content=None, tool_calls=[], raw={})])
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "request_tag_write": {
                    "status": "pending",
                    "request_id": "req-stop-1",
                    "resolved_tag_name": "Globals.bStopButton",
                    "guardrail_passed": True,
                },
                "confirm_tag_write": {
                    "status": "written",
                    "tag_name": "Globals.bStopButton",
                    "written_value": True,
                    "timestamp_utc": "2026-03-06T20:24:43.668120+00:00",
                },
            }
        )
    )  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="stop the machine")
    assert result.answer == "Stop command completed: wrote Globals.bStopButton=True at 2026-03-06T20:24:43.668120+00:00."
    assert [item.tool_name for item in result.tool_trace] == ["request_tag_write", "confirm_tag_write"]
