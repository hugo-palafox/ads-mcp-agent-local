from __future__ import annotations

from typing import Any

from mcp_bridge.transport import AdsMcpTransport


class AdsMcpClient:
    def __init__(self, transport: AdsMcpTransport) -> None:
        self.transport = transport

    def invoke(self, tool_name: str, **arguments: Any) -> Any:
        return self.transport.call_tool(tool_name, arguments)
