from __future__ import annotations

import json
from typing import Any

from agent.models import Message


class Conversation:
    def __init__(self, system_prompt: str) -> None:
        self._messages: list[Message] = [{"role": "system", "content": system_prompt}]

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str | None, tool_calls: list[dict[str, Any]] | None = None) -> None:
        message: Message = {"role": "assistant", "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
        self._messages.append(message)

    def add_tool_result(self, tool_call_id: str, tool_name: str, payload: dict[str, Any]) -> None:
        self._messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": json.dumps(payload, default=str),
            }
        )
