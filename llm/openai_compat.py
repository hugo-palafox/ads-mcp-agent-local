from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from llm.schemas import ModelResponse, ModelToolCall


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def build_payload(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def create_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> ModelResponse:
        payload = self.build_payload(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except TimeoutError as exc:
            raise RuntimeError("Model request timed out") from exc
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Model request failed: HTTP {exc.code} {message}") from exc
        except error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise RuntimeError("Model request timed out") from exc
            raise RuntimeError(f"Model request failed: {exc.reason}") from exc
        return self.parse_response(data)

    def parse_response(self, data: dict[str, Any]) -> ModelResponse:
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("Model response did not contain any choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls: list[ModelToolCall] = []
        for item in tool_calls_raw:
            function = item.get("function") or {}
            name = function.get("name")
            raw_args = function.get("arguments", "{}")
            if not name:
                raise RuntimeError("Tool call missing function name")
            try:
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Malformed tool call arguments for {name}") from exc
            if not isinstance(arguments, dict):
                raise RuntimeError(f"Tool call arguments for {name} must decode to an object")
            tool_calls.append(ModelToolCall(id=item.get("id", name), name=name, arguments=arguments))
        return ModelResponse(content=content, tool_calls=tool_calls, raw=data)
