from __future__ import annotations

import argparse
import json
from typing import Sequence

from agent.orchestrator import AgentOrchestrator
from agent.tool_executor import ToolExecutor
from agent.tool_registry import ToolRegistry
from config.settings import Settings
from llm.client import LLMClient
from mcp_bridge.ads_tools import AdsToolBridge
from mcp_bridge.client import AdsMcpClient
from mcp_bridge.transport import InProcessAdsMcpTransport


def build_orchestrator(settings: Settings) -> AgentOrchestrator:
    transport = InProcessAdsMcpTransport(settings.ads_mcp_server_repo)
    bridge = AdsToolBridge(AdsMcpClient(transport))
    registry = ToolRegistry()
    executor = ToolExecutor(registry, bridge)
    llm_client = LLMClient(settings)
    return AgentOrchestrator(settings, llm_client, registry, executor)


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ads-agent", description="ADS MCP local orchestration agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat", help="Run a chat prompt against a machine context")
    chat_parser.add_argument("--machine", required=True)
    chat_parser.add_argument("--prompt", required=True)
    chat_parser.add_argument("--debug", action="store_true")
    chat_parser.add_argument("--show-tool-trace", action="store_true")
    chat_parser.add_argument("--max-tool-steps", type=int)
    chat_parser.add_argument("--model")
    chat_parser.add_argument("--base-url")

    tools_parser = subparsers.add_parser("tools", help="Tool inspection commands")
    tools_subparsers = tools_parser.add_subparsers(dest="tools_command", required=True)
    tools_subparsers.add_parser("list", help="List model-exposed tools")

    diagnose_model_parser = subparsers.add_parser("diagnose-model", help="Validate model connectivity")
    diagnose_model_parser.add_argument("--model")
    diagnose_model_parser.add_argument("--base-url")

    diagnose_mcp_parser = subparsers.add_parser("diagnose-mcp", help="Validate MCP bridge connectivity")
    diagnose_mcp_parser.add_argument("--machine", default="M1")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "tools" and args.tools_command == "list":
        _print(ToolRegistry().list_for_model())
        return 0

    if args.command == "diagnose-model":
        settings = Settings.from_env()
        if args.model:
            settings.model_name = args.model
        if args.base_url:
            settings.model_base_url = args.base_url
        client = LLMClient(settings)
        response = client.complete(
            messages=[{"role": "user", "content": "Reply with the single word OK."}],
            tools=[],
        )
        _print({"content": response.content, "tool_calls": [call.name for call in response.tool_calls]})
        return 0

    if args.command == "diagnose-mcp":
        settings = Settings.from_env()
        transport = InProcessAdsMcpTransport(settings.ads_mcp_server_repo)
        bridge = AdsToolBridge(AdsMcpClient(transport))
        _print(
            {
                "machine": args.machine,
                "list_groups": bridge.list_groups(args.machine),
                "list_memory_tags": bridge.list_memory_tags(args.machine),
            }
        )
        return 0

    if args.command == "chat":
        settings = Settings.from_env()
        if args.model:
            settings.model_name = args.model
        if args.base_url:
            settings.model_base_url = args.base_url
        if args.max_tool_steps is not None:
            settings.max_tool_steps = args.max_tool_steps
        settings.debug = settings.debug or args.debug
        result = build_orchestrator(settings).run(machine_id=args.machine, prompt=args.prompt)
        print(result.answer)
        if args.show_tool_trace or settings.debug:
            _print([item.to_message_payload() for item in result.tool_trace])
        return 0

    parser.error("Unhandled command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
