from __future__ import annotations

from mcp_bridge.ads_tools import AdsToolBridge
from tests.fixtures.fake_mcp_client import FakeMcpClient


def test_map_tool_calls_correctly() -> None:
    client = FakeMcpClient(responses={"list_groups": ["Globals"]})
    bridge = AdsToolBridge(client)  # type: ignore[arg-type]
    assert bridge.list_groups("M1") == ["Globals"]


def test_pass_machine_id_correctly() -> None:
    client = FakeMcpClient(responses={"read_memory": {"a": 1}})
    bridge = AdsToolBridge(client)  # type: ignore[arg-type]
    bridge.read_memory("M1")
    assert client.calls[0] == ("read_memory", {"machine_id": "M1"})


def test_transform_responses_correctly() -> None:
    client = FakeMcpClient(responses={"read_tag": {"tag_name": "Globals.bRun", "value": True}})
    bridge = AdsToolBridge(client)  # type: ignore[arg-type]
    result = bridge.read_tag("M1", "Globals.bRun")
    assert result["value"] is True


def test_write_tool_calls_map_correctly() -> None:
    client = FakeMcpClient(
        responses={
            "request_tag_write": {"status": "pending", "request_id": "r1", "resolved_tag_name": "Main.startButton"},
            "confirm_tag_write": {"status": "written", "tag_name": "Main.startButton", "written_value": True},
        }
    )
    bridge = AdsToolBridge(client)  # type: ignore[arg-type]
    pending = bridge.request_tag_write("M1", "startButton", True)
    written = bridge.confirm_tag_write("M1", "r1", True)
    assert pending["status"] == "pending"
    assert written["status"] == "written"
