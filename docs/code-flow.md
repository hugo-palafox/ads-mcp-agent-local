# Code Flow

## Chat flow

1. `ads-agent chat` receives `machine`, `prompt`, and optional debug flags.
2. `cli/main.py` builds `Settings`, then constructs the orchestrator stack.
3. `AgentOrchestrator.run()` creates a `Conversation` with the system prompt and user prompt.
4. `LLMClient.complete()` sends messages and tool definitions to the OpenAI-compatible endpoint.
5. If the model requests tools, `ToolExecutor.execute()` validates the request and dispatches it through `AdsToolBridge`.
6. `AdsMcpClient.invoke()` calls the configured transport.
7. `InProcessAdsMcpTransport` imports `ads-mcp-server` tool functions and executes the requested server tool.
8. Tool results are appended back into the conversation as `tool` messages.
9. If `request_tag_write` returns `status: "pending"`, the orchestrator asks the CLI confirmer for explicit user approval.
10. The orchestrator performs `confirm_tag_write` internally (not model-exposed), appends that result, and then continues the loop.
11. The orchestrator calls the model again until it gets a final answer or hits a guardrail.
12. The CLI prints the final answer and optional tool trace.

## Write confirmation branch

1. The model calls `request_tag_write(machine_id, tag_query, value)`.
2. The server validates write guardrails and returns either `rejected` or `pending`.
3. For `pending`, the CLI prompts the user with resolved tag, value, and request id.
4. User approval triggers `confirm_tag_write(..., confirmed=true)`.
5. User denial or non-interactive mode triggers `confirm_tag_write(..., confirmed=false)`.
6. The final answer must be grounded in the confirmation result (`written`, `cancelled`, `expired`, or `rejected`).

## Error flow

1. The model requests a tool.
2. Validation fails or the MCP bridge raises an exception.
3. `ToolExecutor` converts the exception into a structured failed `ToolExecutionResult`.
4. The orchestrator appends the error payload as a tool message.
5. The model gets a chance to respond with a grounded failure explanation.
6. If failures repeat beyond `max_tool_failures`, the orchestrator stops with a structured error answer.
