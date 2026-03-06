from __future__ import annotations

from typing import Any

from agent.models import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {
            "list_groups": ToolDefinition(
                name="list_groups",
                description="List discovered PLC groups for a machine.",
                parameters={
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string", "description": "Machine identifier such as M1."},
                    },
                    "required": ["machine_id"],
                },
                required=("machine_id",),
            ),
            "list_memory_tags": ToolDefinition(
                name="list_memory_tags",
                description="List the curated memory tags configured for a machine.",
                parameters={
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string", "description": "Machine identifier such as M1."},
                    },
                    "required": ["machine_id"],
                },
                required=("machine_id",),
            ),
            "read_tag": ToolDefinition(
                name="read_tag",
                description="Read a specific PLC tag by exact tag name.",
                parameters={
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string", "description": "Machine identifier such as M1."},
                        "tag_name": {"type": "string", "description": "Exact PLC tag name."},
                    },
                    "required": ["machine_id", "tag_name"],
                },
                required=("machine_id", "tag_name"),
            ),
            "read_memory": ToolDefinition(
                name="read_memory",
                description="Read the curated memory set for a machine.",
                parameters={
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string", "description": "Machine identifier such as M1."},
                    },
                    "required": ["machine_id"],
                },
                required=("machine_id",),
            ),
        }

    def get(self, tool_name: str) -> ToolDefinition:
        try:
            return self._tools[tool_name]
        except KeyError as exc:
            raise ValueError(f"Unknown tool: {tool_name}") from exc

    def list_for_model(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    def validate(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        definition = self.get(tool_name)
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be an object")
        missing = [name for name in definition.required if name not in arguments or arguments[name] in (None, "")]
        if missing:
            raise ValueError(f"Missing required arguments for {tool_name}: {', '.join(missing)}")
        allowed = set(definition.parameters["properties"].keys())
        unexpected = sorted(set(arguments) - allowed)
        if unexpected:
            raise ValueError(f"Unexpected arguments for {tool_name}: {', '.join(unexpected)}")
        return arguments
