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


def test_write_flow_confirmed() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="1",
                        name="request_tag_write",
                        arguments={"tag_query": "startButton", "value": True},
                    )
                ],
                raw={},
            ),
            ModelResponse(content="Write completed.", tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "request_tag_write": {
                    "status": "pending",
                    "request_id": "req-1",
                    "resolved_tag_name": "Main.startButton",
                    "guardrail_passed": True,
                },
                "confirm_tag_write": {
                    "status": "written",
                    "tag_name": "Main.startButton",
                    "written_value": True,
                    "timestamp_utc": "2026-03-06T00:00:00Z",
                },
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
    result = orchestrator.run(machine_id="M1", prompt="Turn on the start button.")
    assert result.answer == "Write completed."
    assert [item.tool_name for item in result.tool_trace] == ["request_tag_write", "confirm_tag_write"]
    assert result.tool_trace[1].output["status"] == "written"


def test_write_flow_cancelled_when_denied() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="1",
                        name="request_tag_write",
                        arguments={"tag_query": "startButton", "value": False},
                    )
                ],
                raw={},
            ),
            ModelResponse(content="Write cancelled.", tool_calls=[], raw={}),
        ]
    )
    bridge_client = FakeMcpClient(
        responses={
            "request_tag_write": {
                "status": "pending",
                "request_id": "req-2",
                "resolved_tag_name": "Main.startButton",
                "guardrail_passed": True,
            },
            "confirm_tag_write": {
                "status": "cancelled",
                "tag_name": "Main.startButton",
                "reason": "User declined confirmation",
                "timestamp_utc": "2026-03-06T00:01:00Z",
            },
        }
    )
    bridge = AdsToolBridge(bridge_client)  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(
        sample_settings(),
        llm,
        ToolRegistry(),
        ToolExecutor(ToolRegistry(), bridge),
        write_confirmer=lambda pending: False,
    )
    result = orchestrator.run(machine_id="M1", prompt="Turn off the start button.")
    assert result.answer == "Write cancelled."
    assert result.tool_trace[1].output["status"] == "cancelled"
    assert bridge_client.calls[1] == (
        "confirm_tag_write",
        {"machine_id": "M1", "request_id": "req-2", "confirmed": False},
    )


def test_write_flow_expired_status_is_reported() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="1",
                        name="request_tag_write",
                        arguments={"tag_query": "startButton", "value": True},
                    )
                ],
                raw={},
            ),
            ModelResponse(content="Write request expired before confirmation.", tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "request_tag_write": {
                    "status": "pending",
                    "request_id": "req-3",
                    "resolved_tag_name": "Main.startButton",
                    "guardrail_passed": True,
                },
                "confirm_tag_write": {
                    "status": "expired",
                    "tag_name": "Main.startButton",
                    "reason": "Request expired",
                },
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
    result = orchestrator.run(machine_id="M1", prompt="Turn on the start button.")
    assert result.answer == "Write request expired before confirmation."
    assert result.tool_trace[1].output["status"] == "expired"


def test_write_flow_auto_cancels_without_confirmer() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="1",
                        name="request_tag_write",
                        arguments={"tag_query": "startButton", "value": True},
                    )
                ],
                raw={},
            ),
            ModelResponse(content="Write was not confirmed.", tool_calls=[], raw={}),
        ]
    )
    bridge_client = FakeMcpClient(
        responses={
            "request_tag_write": {
                "status": "pending",
                "request_id": "req-4",
                "resolved_tag_name": "Main.startButton",
                "guardrail_passed": True,
            },
            "confirm_tag_write": {
                "status": "cancelled",
                "tag_name": "Main.startButton",
                "reason": "Confirmation not provided",
                "timestamp_utc": "2026-03-06T00:02:00Z",
            },
        }
    )
    bridge = AdsToolBridge(bridge_client)  # type: ignore[arg-type]
    orchestrator = AgentOrchestrator(sample_settings(), llm, ToolRegistry(), ToolExecutor(ToolRegistry(), bridge))
    result = orchestrator.run(machine_id="M1", prompt="Turn on the start button.")
    assert result.answer == "Write was not confirmed."
    assert bridge_client.calls[1][0] == "confirm_tag_write"
    assert bridge_client.calls[1][1]["confirmed"] is False


def test_write_flow_rejected_status_is_reported() -> None:
    llm = FakeLLMClient(
        [
            ModelResponse(
                content=None,
                tool_calls=[
                    ModelToolCall(
                        id="1",
                        name="request_tag_write",
                        arguments={"tag_query": "startButton", "value": True},
                    )
                ],
                raw={},
            ),
            ModelResponse(content="Write was rejected.", tool_calls=[], raw={}),
        ]
    )
    bridge = AdsToolBridge(
        FakeMcpClient(
            responses={
                "request_tag_write": {
                    "status": "pending",
                    "request_id": "req-5",
                    "resolved_tag_name": "Main.startButton",
                    "guardrail_passed": True,
                },
                "confirm_tag_write": {
                    "status": "rejected",
                    "tag_name": "Main.startButton",
                    "reason": "Unknown request id",
                },
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
    result = orchestrator.run(machine_id="M1", prompt="Turn on the start button.")
    assert result.answer == "Write was rejected."
    assert result.tool_trace[1].output["status"] == "rejected"
