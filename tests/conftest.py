from __future__ import annotations

import pytest

from agent.tool_executor import ToolExecutor
from agent.tool_registry import ToolRegistry
from mcp_bridge.ads_tools import AdsToolBridge
from tests.fixtures.fake_mcp_client import FakeMcpClient
from tests.fixtures.sample_configs import sample_settings


@pytest.fixture
def settings():
    return sample_settings()


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def fake_mcp_client() -> FakeMcpClient:
    return FakeMcpClient()


@pytest.fixture
def bridge(fake_mcp_client: FakeMcpClient) -> AdsToolBridge:
    return AdsToolBridge(fake_mcp_client)  # type: ignore[arg-type]


@pytest.fixture
def executor(registry: ToolRegistry, bridge: AdsToolBridge) -> ToolExecutor:
    return ToolExecutor(registry, bridge)
