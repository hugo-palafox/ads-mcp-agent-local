from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Callable
from typing import Sequence

from agent.orchestrator import AgentOrchestrator
from agent.tool_executor import ToolExecutor
from agent.tool_registry import ToolRegistry
from config.settings import Settings
from llm.client import LLMClient
from mcp_bridge.ads_tools import AdsToolBridge
from mcp_bridge.client import AdsMcpClient
from mcp_bridge.transport import InProcessAdsMcpTransport


def build_orchestrator(
    settings: Settings,
    write_confirmer: Callable[[dict[str, Any]], bool] | None = None,
) -> AgentOrchestrator:
    transport = InProcessAdsMcpTransport(settings.ads_mcp_server_repo)
    bridge = AdsToolBridge(AdsMcpClient(transport))
    registry = ToolRegistry()
    executor = ToolExecutor(registry, bridge)
    llm_client = LLMClient(settings)
    return AgentOrchestrator(settings, llm_client, registry, executor, write_confirmer=write_confirmer)


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def _print_tool_trace_pretty(tool_trace: list[Any]) -> None:
    print("Tool Trace:")
    if not tool_trace:
        print("- (no tool calls)")
        return
    for idx, item in enumerate(tool_trace, start=1):
        status = "OK" if item.ok else "ERROR"
        print(f"{idx}. {item.tool_name} [{status}]")
        if not item.ok:
            print(f"   Error: {item.error}")
            continue
        output = item.output
        if item.tool_name == "read_memory" and isinstance(output, dict):
            if not output:
                print("   Result: <empty>")
            else:
                key_values = ", ".join(f"{k}={v}" for k, v in output.items())
                print(f"   Result: {key_values}")
            continue
        if item.tool_name == "request_tag_write" and isinstance(output, dict):
            print(
                "   Result: "
                f"status={output.get('status')}, "
                f"request_id={output.get('request_id')}, "
                f"resolved_tag_name={output.get('resolved_tag_name')}"
            )
            continue
        if item.tool_name == "confirm_tag_write" and isinstance(output, dict):
            print(
                "   Result: "
                f"status={output.get('status')}, "
                f"tag_name={output.get('tag_name')}, "
                f"written_value={output.get('written_value')}"
            )
            continue
        print(f"   Result: {json.dumps(output, default=str)}")


def _make_write_confirmer() -> Callable[[dict[str, Any]], bool]:
    interactive = sys.stdin.isatty() and sys.stdout.isatty()

    def confirm(pending: dict[str, Any]) -> bool:
        request_id = pending.get("request_id")
        tag_name = pending.get("resolved_tag_name")
        value = pending.get("value")
        machine_id = pending.get("machine_id")
        if not interactive:
            print(
                "Write confirmation requires interactive input. "
                f"Auto-cancelling request_id={request_id} machine={machine_id} tag={tag_name} value={value}."
            )
            return False
        answer = input(
            "Confirm PLC write "
            f"(machine={machine_id}, tag={tag_name}, value={value}, request_id={request_id}) [y/N]: "
        ).strip().lower()
        return answer in {"y", "yes"}

    return confirm


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ads-agent", description="ADS MCP local orchestration agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat_parser = subparsers.add_parser("chat", help="Run a chat prompt against a machine context")
    chat_parser.add_argument("--machine", required=True)
    chat_parser.add_argument("--prompt", required=True)
    chat_parser.add_argument("--debug", action="store_true")
    chat_parser.add_argument("--show-tool-trace", action="store_true")
    chat_parser.add_argument("--tool-trace-format", choices=("json", "pretty"), default="json")
    chat_parser.add_argument("--max-tool-steps", type=int)
    chat_parser.add_argument("--model")
    chat_parser.add_argument("--base-url")
    chat_parser.add_argument("--timeout-seconds", type=float)
    chat_timing_group = chat_parser.add_mutually_exclusive_group()
    chat_timing_group.add_argument(
        "--show-timing",
        dest="show_timing",
        action="store_true",
        default=True,
        help="Show response time in seconds (default: enabled).",
    )
    chat_timing_group.add_argument(
        "--hide-timing",
        dest="show_timing",
        action="store_false",
        help="Hide response time output.",
    )

    tools_parser = subparsers.add_parser("tools", help="Tool inspection commands")
    tools_subparsers = tools_parser.add_subparsers(dest="tools_command", required=True)
    tools_subparsers.add_parser("list", help="List model-exposed tools")

    diagnose_model_parser = subparsers.add_parser("diagnose-model", help="Validate model connectivity")
    diagnose_model_parser.add_argument("--model")
    diagnose_model_parser.add_argument("--base-url")
    diagnose_model_parser.add_argument("--timeout-seconds", type=float)

    model_chat_parser = subparsers.add_parser("model-chat", help="Send a direct prompt to the model without tools")
    model_chat_parser.add_argument("--prompt", required=True)
    model_chat_parser.add_argument("--model")
    model_chat_parser.add_argument("--base-url")
    model_chat_parser.add_argument("--timeout-seconds", type=float)
    model_timing_group = model_chat_parser.add_mutually_exclusive_group()
    model_timing_group.add_argument(
        "--show-timing",
        dest="show_timing",
        action="store_true",
        default=True,
        help="Show response time in seconds (default: enabled).",
    )
    model_timing_group.add_argument(
        "--hide-timing",
        dest="show_timing",
        action="store_false",
        help="Hide response time output.",
    )

    diagnose_mcp_parser = subparsers.add_parser("diagnose-mcp", help="Validate MCP bridge connectivity")
    diagnose_mcp_parser.add_argument("--machine", default="M1")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "tools" and args.tools_command == "list":
            _print(ToolRegistry().list_for_model())
            return 0

        if args.command == "diagnose-model":
            settings = Settings.from_env()
            if args.model:
                settings.model_name = args.model
            if args.base_url:
                settings.model_base_url = args.base_url
            if args.timeout_seconds is not None:
                settings.timeout_seconds = args.timeout_seconds
            client = LLMClient(settings)
            response = client.complete(
                messages=[{"role": "user", "content": "Reply with the single word OK."}],
                tools=[],
            )
            _print({"content": response.content, "tool_calls": [call.name for call in response.tool_calls]})
            return 0

        if args.command == "model-chat":
            settings = Settings.from_env()
            if args.model:
                settings.model_name = args.model
            if args.base_url:
                settings.model_base_url = args.base_url
            if args.timeout_seconds is not None:
                settings.timeout_seconds = args.timeout_seconds
            started_at = time.perf_counter()
            client = LLMClient(settings)
            response = client.complete(
                messages=[{"role": "user", "content": args.prompt}],
                tools=[],
            )
            print(response.content or "No answer returned by the model.")
            if args.show_timing:
                elapsed = time.perf_counter() - started_at
                print(f"Response time: {elapsed:.3f}s")
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
            if args.timeout_seconds is not None:
                settings.timeout_seconds = args.timeout_seconds
            if args.max_tool_steps is not None:
                settings.max_tool_steps = args.max_tool_steps
            settings.debug = settings.debug or args.debug
            started_at = time.perf_counter()
            result = build_orchestrator(settings, write_confirmer=_make_write_confirmer()).run(
                machine_id=args.machine,
                prompt=args.prompt,
            )
            print(result.answer)
            if args.show_tool_trace or settings.debug:
                if args.tool_trace_format == "pretty":
                    _print_tool_trace_pretty(result.tool_trace)
                else:
                    _print([item.to_message_payload() for item in result.tool_trace])
            if args.show_timing:
                elapsed = time.perf_counter() - started_at
                print(f"Response time: {elapsed:.3f}s")
            return 0
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    parser.error("Unhandled command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
