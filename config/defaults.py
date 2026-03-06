from __future__ import annotations

import os
from pathlib import Path

DEFAULT_MODEL_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL_API_KEY = "ollama"
DEFAULT_MODEL_NAME = "qwen3:8b"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 800
DEFAULT_MAX_TOOL_STEPS = 4
DEFAULT_MAX_TOOL_FAILURES = 2
DEFAULT_DEBUG = False
if os.name == "nt":
    DEFAULT_ADS_MCP_SERVER_REPO = str(Path.home() / "source" / "repos" / "ads-mcp-server")
else:
    DEFAULT_ADS_MCP_SERVER_REPO = "/mnt/c/Users/hugod/source/repos/ads-mcp-server"
DEFAULT_ADS_MCP_TRANSPORT = "inprocess"
