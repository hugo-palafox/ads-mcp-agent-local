from __future__ import annotations

from typing import Any


class FakeMcpClient:
    def __init__(self, responses: dict[str, Any] | None = None, errors: dict[str, Exception] | None = None) -> None:
        self.responses = responses or {}
        self.errors = errors or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def invoke(self, tool_name: str, **arguments: Any) -> Any:
        self.calls.append((tool_name, arguments))
        if tool_name in self.errors:
            raise self.errors[tool_name]
        return self.responses[tool_name]
