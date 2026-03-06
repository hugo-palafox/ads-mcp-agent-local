from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


Message = dict[str, Any]


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    required: tuple[str, ...]


@dataclass(slots=True)
class ToolExecutionResult:
    tool_name: str
    arguments: dict[str, Any]
    ok: bool
    output: Any = None
    error: str | None = None

    def to_message_payload(self) -> dict[str, Any]:
        payload = {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "ok": self.ok,
        }
        if self.ok:
            payload["result"] = self.output
        else:
            payload["error"] = self.error
        return payload


@dataclass(slots=True)
class AgentRunResult:
    answer: str
    messages: list[Message]
    tool_trace: list[ToolExecutionResult] = field(default_factory=list)
    iterations: int = 0
