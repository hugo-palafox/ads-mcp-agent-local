from __future__ import annotations

import json
from typing import Any, Callable

from agent.conversation import Conversation
from agent.models import AgentRunResult
from agent.prompts import build_system_prompt
from agent.tool_executor import ToolExecutor
from agent.tool_registry import ToolRegistry
from config.settings import Settings
from llm.client import LLMClient


class AgentOrchestrator:
    def __init__(
        self,
        settings: Settings,
        llm_client: LLMClient,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        write_confirmer: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
        self.write_confirmer = write_confirmer

    def run(self, *, machine_id: str, prompt: str) -> AgentRunResult:
        conversation = Conversation(build_system_prompt(machine_id))
        conversation.add_user(prompt)
        tool_trace = []
        failed_tool_calls = 0

        for iteration in range(1, self.settings.max_tool_steps + 1):
            response = self.llm_client.complete(conversation.messages, self.tool_registry.list_for_model())
            conversation.add_assistant(response.content, [
                {
                    "id": call.id,
                    "type": "function",
                    # OpenAI-compatible APIs expect function.arguments as a JSON string.
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                }
                for call in response.tool_calls
            ] if response.tool_calls else None)

            if not response.tool_calls:
                answer = response.content or self._fallback_answer_for_empty_content(tool_trace)
                return AgentRunResult(
                    answer=answer,
                    messages=conversation.messages,
                    tool_trace=tool_trace,
                    iterations=iteration,
                )

            for tool_call in response.tool_calls:
                arguments = dict(tool_call.arguments)
                arguments.setdefault("machine_id", machine_id)
                result = self.tool_executor.execute(tool_call.name, arguments)
                tool_trace.append(result)
                conversation.add_tool_result(tool_call.id, tool_call.name, result.to_message_payload())
                if not result.ok:
                    failed_tool_calls += 1
                    if failed_tool_calls >= self.settings.max_tool_failures:
                        return AgentRunResult(
                            answer=f"Stopped after repeated tool failures. Last error: {result.error}",
                            messages=conversation.messages,
                            tool_trace=tool_trace,
                            iterations=iteration,
                        )
                    continue

                pending_request = self._extract_pending_request(result.output, arguments)
                if tool_call.name == "request_tag_write" and pending_request is not None:
                    confirmed = self.write_confirmer(pending_request) if self.write_confirmer is not None else False
                    confirm_call_id = f"{tool_call.id}:confirm"
                    confirm_arguments = {
                        "machine_id": machine_id,
                        "request_id": pending_request["request_id"],
                        "confirmed": bool(confirmed),
                    }
                    conversation.add_assistant(
                        content=None,
                        tool_calls=[
                            {
                                "id": confirm_call_id,
                                "type": "function",
                                "function": {
                                    "name": "confirm_tag_write",
                                    "arguments": json.dumps(confirm_arguments),
                                },
                            }
                        ],
                    )
                    confirm_result = self.tool_executor.execute_internal("confirm_tag_write", confirm_arguments)
                    tool_trace.append(confirm_result)
                    conversation.add_tool_result(confirm_call_id, "confirm_tag_write", confirm_result.to_message_payload())
                    if not confirm_result.ok:
                        failed_tool_calls += 1
                        if failed_tool_calls >= self.settings.max_tool_failures:
                            return AgentRunResult(
                                answer=f"Stopped after repeated tool failures. Last error: {confirm_result.error}",
                                messages=conversation.messages,
                                tool_trace=tool_trace,
                                iterations=iteration,
                            )

        return AgentRunResult(
            answer="Stopped before completion because the maximum tool iteration limit was reached.",
            messages=conversation.messages,
            tool_trace=tool_trace,
            iterations=self.settings.max_tool_steps,
        )

    def _fallback_answer_for_empty_content(self, tool_trace: list) -> str:
        if not tool_trace:
            return "No answer returned by the model."

        last = tool_trace[-1]
        if last.ok and last.tool_name == "read_memory" and isinstance(last.output, dict) and not last.output:
            return (
                "No memory values were returned for this machine. "
                "Configure memory tags in ads-mcp-server and try again."
            )

        if last.ok and last.tool_name == "list_memory_tags" and isinstance(last.output, list) and not last.output:
            return (
                "No curated memory tags are configured for this machine. "
                "Use ads-mcp-server setup/discovery commands, then add memory tags."
            )

        return (
            "No answer returned by the model after tool execution. "
            f"Last tool: {last.tool_name} (ok={last.ok})."
        )

    def _extract_pending_request(self, output: Any, arguments: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(output, dict):
            return None
        if output.get("status") != "pending":
            return None
        request_id = output.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            return None
        return {
            "request_id": request_id,
            "resolved_tag_name": output.get("resolved_tag_name"),
            "value": arguments.get("value"),
            "machine_id": arguments.get("machine_id"),
        }
