from __future__ import annotations

from agent.models import ToolExecutionResult
from agent.tool_registry import ToolRegistry
from mcp_bridge.ads_tools import AdsToolBridge


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, bridge: AdsToolBridge) -> None:
        self.registry = registry
        self.bridge = bridge

    def execute(self, tool_name: str, arguments: dict[str, object]) -> ToolExecutionResult:
        try:
            validated = self.registry.validate(tool_name, arguments)
            return self._invoke(tool_name, validated)
        except Exception as exc:
            return ToolExecutionResult(tool_name=tool_name, arguments=arguments, ok=False, error=str(exc))

    def execute_internal(self, tool_name: str, arguments: dict[str, object]) -> ToolExecutionResult:
        try:
            return self._invoke(tool_name, arguments)
        except Exception as exc:
            return ToolExecutionResult(tool_name=tool_name, arguments=arguments, ok=False, error=str(exc))

    def _invoke(self, tool_name: str, arguments: dict[str, object]) -> ToolExecutionResult:
        handler = getattr(self.bridge, tool_name)
        output = handler(**arguments)
        return ToolExecutionResult(tool_name=tool_name, arguments=arguments, ok=True, output=output)
