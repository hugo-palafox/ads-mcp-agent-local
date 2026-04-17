from __future__ import annotations

from typing import Any

from config.settings import Settings
from llm.openai_compat import OpenAICompatClient
from llm.schemas import ModelResponse


class LLMClient:
    def __init__(self, settings: Settings, transport: OpenAICompatClient | None = None) -> None:
        self.settings = settings
        self.transport = transport or OpenAICompatClient(
            base_url=settings.model_base_url,
            api_key=settings.model_api_key,
            timeout_seconds=settings.timeout_seconds,
        )

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelResponse:
        return self.transport.create_chat_completion(
            model=self.settings.model_name,
            messages=messages,
            tools=tools,
            thinking=self.settings.model_thinking,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )
