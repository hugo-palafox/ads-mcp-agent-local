from __future__ import annotations

from config.settings import Settings


def sample_settings() -> Settings:
    settings = Settings.from_env()
    settings.model_base_url = "http://localhost:11434/v1"
    settings.model_api_key = "ollama"
    settings.model_name = "qwen3:8b"
    settings.max_tool_steps = 4
    settings.max_tool_failures = 2
    return settings
