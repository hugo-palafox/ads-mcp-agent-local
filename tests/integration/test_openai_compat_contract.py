from __future__ import annotations

from llm.openai_compat import OpenAICompatClient
from tests.fixtures.fake_model_responses import tool_call_response


def test_openai_compat_contract() -> None:
    client = OpenAICompatClient(base_url="http://localhost:11434/v1", api_key="ollama")
    payload = client.build_payload(
        model="qwen3:8b",
        messages=[{"role": "user", "content": "state?"}],
        tools=[{"type": "function", "function": {"name": "read_memory", "parameters": {"type": "object"}}}],
        temperature=0.1,
        max_tokens=100,
    )
    parsed = client.parse_response(tool_call_response(tool_call_id="call_123", tool_name="read_memory", arguments='{"machine_id": "M1"}'))
    assert payload["tools"][0]["function"]["name"] == "read_memory"
    assert parsed.tool_calls[0].id == "call_123"
