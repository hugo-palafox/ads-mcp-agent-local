from __future__ import annotations

import pytest

from llm.openai_compat import OpenAICompatClient
from tests.fixtures.fake_model_responses import final_response, tool_call_response


def test_builds_request_payload_correctly() -> None:
    client = OpenAICompatClient(base_url="http://localhost:11434/v1", api_key="ollama")
    payload = client.build_payload(
        model="qwen3:8b",
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "read_memory"}}],
        temperature=0.2,
        max_tokens=100,
    )
    assert payload["model"] == "qwen3:8b"
    assert payload["tool_choice"] == "auto"
    assert payload["messages"][0]["content"] == "hi"


def test_handles_api_response_format_correctly() -> None:
    client = OpenAICompatClient(base_url="http://localhost:11434/v1", api_key="ollama")
    response = client.parse_response(tool_call_response(tool_call_id="call_1", tool_name="read_memory", arguments='{"machine_id": "M1"}'))
    assert response.tool_calls[0].name == "read_memory"
    assert response.tool_calls[0].arguments["machine_id"] == "M1"


def test_handles_empty_responses() -> None:
    client = OpenAICompatClient(base_url="http://localhost:11434/v1", api_key="ollama")
    with pytest.raises(RuntimeError, match="did not contain any choices"):
        client.parse_response({})


def test_handles_malformed_tool_response_content() -> None:
    client = OpenAICompatClient(base_url="http://localhost:11434/v1", api_key="ollama")
    with pytest.raises(RuntimeError, match="Malformed tool call arguments"):
        client.parse_response(tool_call_response(tool_call_id="call_1", tool_name="read_memory", arguments='{"machine_id":'))


def test_handles_timeout_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAICompatClient(base_url="http://localhost:11434/v1", api_key="ollama")

    def fake_urlopen(req, timeout):
        raise TimeoutError("timeout")

    monkeypatch.setattr("llm.openai_compat.request.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="timed out"):
        client.create_chat_completion(
            model="qwen3:8b",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            temperature=0.1,
            max_tokens=50,
        )


def test_parses_plain_final_response() -> None:
    client = OpenAICompatClient(base_url="http://localhost:11434/v1", api_key="ollama")
    response = client.parse_response(final_response("OK"))
    assert response.content == "OK"
    assert response.tool_calls == []
