from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from config import defaults


@dataclass(slots=True)
class Settings:
    model_base_url: str = defaults.DEFAULT_MODEL_BASE_URL
    model_api_key: str = defaults.DEFAULT_MODEL_API_KEY
    model_name: str = defaults.DEFAULT_MODEL_NAME
    model_thinking: bool | None = defaults.DEFAULT_MODEL_THINKING
    timeout_seconds: float = defaults.DEFAULT_TIMEOUT_SECONDS
    temperature: float = defaults.DEFAULT_TEMPERATURE
    max_tokens: int = defaults.DEFAULT_MAX_TOKENS
    debug: bool = defaults.DEFAULT_DEBUG
    max_tool_steps: int = defaults.DEFAULT_MAX_TOOL_STEPS
    max_tool_failures: int = defaults.DEFAULT_MAX_TOOL_FAILURES
    ads_mcp_server_repo: str = defaults.DEFAULT_ADS_MCP_SERVER_REPO
    ads_mcp_transport: str = defaults.DEFAULT_ADS_MCP_TRANSPORT
    teaching_store_dir: str = defaults.DEFAULT_TEACHING_STORE_DIR

    @classmethod
    def from_env(cls) -> "Settings":
        raw_server_repo = os.getenv("ADS_AGENT_MCP_SERVER_REPO", defaults.DEFAULT_ADS_MCP_SERVER_REPO)
        return cls(
            model_base_url=os.getenv("ADS_AGENT_MODEL_BASE_URL", defaults.DEFAULT_MODEL_BASE_URL),
            model_api_key=os.getenv("ADS_AGENT_MODEL_API_KEY", defaults.DEFAULT_MODEL_API_KEY),
            model_name=os.getenv("ADS_AGENT_MODEL_NAME", defaults.DEFAULT_MODEL_NAME),
            model_thinking=_env_optional_bool("ADS_AGENT_MODEL_THINKING", defaults.DEFAULT_MODEL_THINKING),
            timeout_seconds=float(os.getenv("ADS_AGENT_TIMEOUT_SECONDS", defaults.DEFAULT_TIMEOUT_SECONDS)),
            temperature=float(os.getenv("ADS_AGENT_TEMPERATURE", defaults.DEFAULT_TEMPERATURE)),
            max_tokens=int(os.getenv("ADS_AGENT_MAX_TOKENS", defaults.DEFAULT_MAX_TOKENS)),
            debug=_env_bool("ADS_AGENT_DEBUG", defaults.DEFAULT_DEBUG),
            max_tool_steps=int(os.getenv("ADS_AGENT_MAX_TOOL_STEPS", defaults.DEFAULT_MAX_TOOL_STEPS)),
            max_tool_failures=int(os.getenv("ADS_AGENT_MAX_TOOL_FAILURES", defaults.DEFAULT_MAX_TOOL_FAILURES)),
            ads_mcp_server_repo=_normalize_server_repo(raw_server_repo),
            ads_mcp_transport=os.getenv("ADS_AGENT_MCP_TRANSPORT", defaults.DEFAULT_ADS_MCP_TRANSPORT),
            teaching_store_dir=os.getenv("ADS_AGENT_TEACHING_STORE_DIR", defaults.DEFAULT_TEACHING_STORE_DIR),
        )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional_bool(name: str, default: bool | None) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized == "":
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(
        f"Invalid boolean value for {name}: {value!r}. "
        "Use one of: true/false, 1/0, yes/no, on/off."
    )


def _normalize_server_repo(path_value: str) -> str:
    # Accept WSL-style paths on Windows, e.g. /mnt/c/Users/... -> C:\\Users\\...
    value = path_value.strip()
    if os.name == "nt":
        parts = Path(value).parts
        if len(parts) >= 3 and parts[0] in {"/", "\\"} and parts[1].lower() == "mnt":
            drive = parts[2]
            if len(drive) == 1 and drive.isalpha():
                remainder = parts[3:]
                return str(Path(f"{drive.upper()}:\\", *remainder))
    return value
