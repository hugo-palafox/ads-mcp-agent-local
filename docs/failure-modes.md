# Failure Modes

## Model timeout

`OpenAICompatClient` raises `RuntimeError("Model request timed out")` and the CLI surfaces it as `ERROR: Model request timed out` without a traceback.

Mitigations:

- Increase `ADS_AGENT_TIMEOUT_SECONDS`.
- Override per command with `--timeout-seconds`.
- Expect tool-enabled chats to take longer than `diagnose-model`.
- For thinking-capable models, try `--no-think` or set `ADS_AGENT_MODEL_THINKING=false`.

## Invalid thinking setting

If `ADS_AGENT_MODEL_THINKING` is set to an invalid value, startup fails with a deterministic configuration error. Use one of `true/false`, `1/0`, `yes/no`, or `on/off`.

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
