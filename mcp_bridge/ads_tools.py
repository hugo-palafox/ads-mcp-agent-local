from __future__ import annotations

from typing import Any

from mcp_bridge.client import AdsMcpClient


class AdsToolBridge:
    def __init__(self, client: AdsMcpClient) -> None:
        self.client = client

    def list_machines(self) -> list[dict[str, Any]]:
        return self.client.invoke("list_machines")

    def get_machine(self, machine_id: str) -> dict[str, Any]:
        return self.client.invoke("get_machine", machine_id=machine_id)

    def list_groups(self, machine_id: str) -> list[str]:
        return self.client.invoke("list_groups", machine_id=machine_id)

    def list_discovered_tags(self, machine_id: str) -> list[dict[str, Any]]:
        return self.client.invoke("list_discovered_tags", machine_id=machine_id)

    def list_memory_tags(self, machine_id: str) -> list[dict[str, Any]]:
        return self.client.invoke("list_memory_tags", machine_id=machine_id)

    def read_tag(self, machine_id: str, tag_name: str) -> dict[str, Any]:
        return self.client.invoke("read_tag", machine_id=machine_id, tag_name=tag_name)

    def read_tags(self, machine_id: str, tag_names: list[str]) -> dict[str, Any]:
        return self.client.invoke("read_tags", machine_id=machine_id, tag_names=tag_names)

    def read_memory(self, machine_id: str) -> dict[str, Any]:
        return self.client.invoke("read_memory", machine_id=machine_id)

    def request_tag_write(self, machine_id: str, tag_query: str, value: Any) -> dict[str, Any]:
        return self.client.invoke("request_tag_write", machine_id=machine_id, tag_query=tag_query, value=value)

    def confirm_tag_write(self, machine_id: str, request_id: str, confirmed: bool) -> dict[str, Any]:
        return self.client.invoke("confirm_tag_write", machine_id=machine_id, request_id=request_id, confirmed=confirmed)
