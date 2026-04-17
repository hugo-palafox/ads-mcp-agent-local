from __future__ import annotations

from agent.conversation import Conversation


def test_appends_messages_in_correct_order() -> None:
    conversation = Conversation("system")
    conversation.add_user("hello")
    conversation.add_assistant("hi")
    assert [item["role"] for item in conversation.messages] == ["system", "user", "assistant"]


def test_stores_tool_responses_correctly() -> None:
    conversation = Conversation("system")
    conversation.add_tool_result("call_1", "read_memory", {"ok": True, "result": {"x": 1}})
    message = conversation.messages[-1]
    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call_1"


def test_preserves_system_prompt() -> None:
    conversation = Conversation("keep me")
    conversation.add_user("hello")
    assert conversation.messages[0]["content"] == "keep me"
