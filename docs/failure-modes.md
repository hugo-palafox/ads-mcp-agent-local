# Failure Modes

## Model timeout

`OpenAICompatClient` raises `RuntimeError("Model request timed out")` and the CLI surfaces the failure.

## Malformed tool call

If tool arguments cannot be decoded or are not an object, the model response is rejected as malformed.

## Unknown tool

`ToolRegistry` rejects tools outside the approved list.

## MCP server unavailable

If the local server repo cannot be found or imported, `InProcessAdsMcpTransport` raises a startup error.

## MCP tool returns bad data

The bridge passes the result through, and any downstream formatting issues are surfaced as tool failures.

## Model returns final answer without tool use

The orchestrator accepts the answer as-is. QA should verify whether the prompt should have required a tool.

## Repeated failed tool loops

The orchestrator stops after `max_tool_failures` and returns a deterministic failure answer instead of looping forever.
