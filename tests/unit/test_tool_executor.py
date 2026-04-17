from __future__ import annotations

from tests.fixtures.fake_mcp_client import FakeMcpClient
from mcp_bridge.ads_tools import AdsToolBridge
from agent.tool_executor import ToolExecutor
from agent.tool_registry import ToolRegistry


def test_executes_valid_tool_correctly() -> None:
    client = FakeMcpClient(responses={"read_memory": {"Globals.bRun": True}})
    executor = ToolExecutor(ToolRegistry(), AdsToolBridge(client))  # type: ignore[arg-type]
    result = executor.execute("read_memory", {"machine_id": "M1"})
    assert result.ok is True
    assert result.output["Globals.bRun"] is True


def test_rejects_invalid_tool_name() -> None:
    executor = ToolExecutor(ToolRegistry(), AdsToolBridge(FakeMcpClient()))  # type: ignore[arg-type]
    result = executor.execute("bad_tool", {"machine_id": "M1"})
    assert result.ok is False
    assert "Unknown tool" in (result.error or "")


def test_rejects_invalid_arguments() -> None:
    executor = ToolExecutor(ToolRegistry(), AdsToolBridge(FakeMcpClient()))  # type: ignore[arg-type]
    result = executor.execute("read_tag", {"machine_id": "M1"})
    assert result.ok is False
    assert "Missing required arguments" in (result.error or "")


def test_handles_mcp_failures() -> None:
    client = FakeMcpClient(errors={"read_memory": RuntimeError("PLC offline")})
    executor = ToolExecutor(ToolRegistry(), AdsToolBridge(client))  # type: ignore[arg-type]
    result = executor.execute("read_memory", {"machine_id": "M1"})
    assert result.ok is False
    assert result.error == "PLC offline"


def test_returns_structured_tool_result() -> None:
    client = FakeMcpClient(responses={"list_memory_tags": [{"name": "Globals.bRun"}]})
    executor = ToolExecutor(ToolRegistry(), AdsToolBridge(client))  # type: ignore[arg-type]
    result = executor.execute("list_memory_tags", {"machine_id": "M1"})
    assert result.to_message_payload()["ok"] is True
    assert result.to_message_payload()["result"][0]["name"] == "Globals.bRun"
