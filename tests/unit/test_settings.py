from __future__ import annotations

from config.defaults import DEFAULT_TIMEOUT_SECONDS
from config.settings import Settings
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
