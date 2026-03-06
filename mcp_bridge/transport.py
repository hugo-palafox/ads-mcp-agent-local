from __future__ import annotations

import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol


class AdsMcpTransport(Protocol):
    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        ...


class InProcessAdsMcpTransport:
    def __init__(self, server_repo: str) -> None:
        self.server_repo = Path(server_repo)
        self._tools_module = None

    def _load_tools_module(self):
        if self._tools_module is not None:
            return self._tools_module
        if not self.server_repo.exists():
            raise RuntimeError(f"ADS MCP server repo not found: {self.server_repo}")
        repo_str = str(self.server_repo)
        if repo_str not in sys.path:
            sys.path.insert(0, repo_str)
        try:
            with self._server_repo_cwd():
                self._tools_module = importlib.import_module("mcp_app.tools")
        except Exception as exc:
            raise RuntimeError(f"Unable to import ads-mcp-server tools from {self.server_repo}: {exc}") from exc
        return self._tools_module

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        tools_module = self._load_tools_module()
        handler = getattr(tools_module, tool_name, None)
        if handler is None:
            raise RuntimeError(f"ads-mcp-server does not expose tool '{tool_name}'")
        with self._server_repo_cwd():
            return handler(**arguments)

    @contextmanager
    def _server_repo_cwd(self):
        old_cwd = Path.cwd()
        try:
            os.chdir(self.server_repo)
            yield
        finally:
            os.chdir(old_cwd)
