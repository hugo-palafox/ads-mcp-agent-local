from __future__ import annotations

from config.defaults import DEFAULT_TIMEOUT_SECONDS
from config.settings import Settings
from config.settings import _env_optional_bool
from config.settings import _normalize_server_repo


def test_normalize_server_repo_passes_through_normal_path() -> None:
    value = "C:\\Users\\hugod\\source\\repos\\ads-mcp-server"
    assert _normalize_server_repo(value).endswith("ads-mcp-server")


def test_normalize_server_repo_handles_wsl_style_drive_path() -> None:
    # On non-Windows OS this remains unchanged; on Windows it becomes a drive path.
    value = "/mnt/c/Users/hugod/source/repos/ads-mcp-server"
    normalized = _normalize_server_repo(value)
    assert normalized.endswith("ads-mcp-server")


def test_settings_use_updated_default_timeout(monkeypatch) -> None:
    monkeypatch.delenv("ADS_AGENT_TIMEOUT_SECONDS", raising=False)
    settings = Settings.from_env()
    assert settings.timeout_seconds == DEFAULT_TIMEOUT_SECONDS == 90.0


def test_settings_use_provider_default_thinking_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("ADS_AGENT_MODEL_THINKING", raising=False)
    settings = Settings.from_env()
    assert settings.model_thinking is None


def test_settings_parse_explicit_model_thinking_from_env(monkeypatch) -> None:
    monkeypatch.setenv("ADS_AGENT_MODEL_THINKING", "off")
    settings = Settings.from_env()
    assert settings.model_thinking is False


def test_env_optional_bool_rejects_invalid_value(monkeypatch) -> None:
    monkeypatch.setenv("ADS_AGENT_MODEL_THINKING", "maybe")
    try:
        _env_optional_bool("ADS_AGENT_MODEL_THINKING", None)
    except RuntimeError as exc:
        assert "Invalid boolean value for ADS_AGENT_MODEL_THINKING" in str(exc)
    else:
        raise AssertionError("Expected invalid boolean value to raise RuntimeError")
