from __future__ import annotations

import pytest

from agent.tool_registry import ToolRegistry


def test_registers_expected_tools() -> None:
    registry = ToolRegistry()
    tool_names = [item["function"]["name"] for item in registry.list_for_model()]
    assert tool_names == ["list_groups", "list_memory_tags", "read_tag", "read_memory"]


def test_validates_schemas() -> None:
    registry = ToolRegistry()
    args = registry.validate("read_tag", {"machine_id": "M1", "tag_name": "Globals.bRun"})
    assert args["tag_name"] == "Globals.bRun"


def test_rejects_unknown_tools() -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="Unknown tool"):
        registry.get("does_not_exist")
