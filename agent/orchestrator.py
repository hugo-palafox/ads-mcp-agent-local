from __future__ import annotations

import json

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
    ) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor

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
                answer = response.content or "No answer returned by the model."
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

        return AgentRunResult(
            answer="Stopped before completion because the maximum tool iteration limit was reached.",
            messages=conversation.messages,
            tool_trace=tool_trace,
            iterations=self.settings.max_tool_steps,
        )
