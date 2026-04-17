from __future__ import annotations


def tool_call_response(*, tool_call_id: str, tool_name: str, arguments: str, content: str | None = None) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": content,
                    "tool_calls": [
                        {
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": arguments,
                            },
                        }
                    ],
                }
            }
        ]
    }


def final_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}
