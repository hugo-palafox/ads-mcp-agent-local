from __future__ import annotations

from config.settings import _normalize_server_repo


def test_normalize_server_repo_passes_through_normal_path() -> None:
    value = "C:\\Users\\hugod\\source\\repos\\ads-mcp-server"
    assert _normalize_server_repo(value).endswith("ads-mcp-server")


def test_normalize_server_repo_handles_wsl_style_drive_path() -> None:
    # On non-Windows OS this remains unchanged; on Windows it becomes a drive path.
    value = "/mnt/c/Users/hugod/source/repos/ads-mcp-server"
    normalized = _normalize_server_repo(value)
    assert normalized.endswith("ads-mcp-server")
