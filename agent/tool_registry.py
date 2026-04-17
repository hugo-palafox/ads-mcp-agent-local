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
            "request_tag_write": ToolDefinition(
                name="request_tag_write",
                description="Request a guarded PLC write for a machine. This does not write immediately.",
                parameters={
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string", "description": "Machine identifier such as M1."},
                        "tag_query": {"type": "string", "description": "Exact or partial PLC tag query."},
                        "value": {
                            "description": "Requested JSON scalar value.",
                            "anyOf": [
                                {"type": "boolean"},
                                {"type": "integer"},
                                {"type": "number"},
                                {"type": "string"},
                            ],
                        },
                    },
                    "required": ["machine_id", "tag_query", "value"],
                },
                required=("machine_id", "tag_query", "value"),
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
        for name, schema in definition.parameters["properties"].items():
            if name in arguments and not self._matches_schema(arguments[name], schema):
                raise ValueError(f"Invalid argument type for {tool_name}.{name}")
        return arguments

    def _matches_schema(self, value: Any, schema: dict[str, Any]) -> bool:
        if "anyOf" in schema:
            return any(self._matches_schema(value, child) for child in schema["anyOf"])
        expected = schema.get("type")
        if expected is None:
            return True
        if expected == "string":
            return isinstance(value, str)
        if expected == "boolean":
            return isinstance(value, bool)
        if expected == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected == "number":
            return (isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float)
        if expected == "object":
            return isinstance(value, dict)
        if expected == "array":
            return isinstance(value, list)
        if expected == "null":
            return value is None
        return True
