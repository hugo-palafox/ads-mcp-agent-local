# Architecture

`ads-mcp-agent-local` has five layers.

1. CLI layer: `cli/main.py` parses local commands and prints answers and tool traces.
2. Orchestrator layer: `agent/orchestrator.py` runs the model-tool loop with iteration and failure guards.
3. Tool execution layer: `agent/tool_registry.py` and `agent/tool_executor.py` define exposed tools, validate arguments, and normalize results.
4. MCP bridge layer: `mcp_bridge/client.py`, `mcp_bridge/ads_tools.py`, and `mcp_bridge/transport.py` isolate all access to `ads-mcp-server`.
5. Model layer: `llm/openai_compat.py` and `llm/client.py` speak to OpenAI-compatible endpoints such as Ollama.

## Separation of responsibilities

- The model layer only knows about messages, tools, and OpenAI-style payloads.
- The orchestrator decides when to continue, stop, or surface tool failures.
- The MCP bridge owns the server integration contract and hides local transport details.
- `ads-mcp-server` remains unchanged and reusable.

## Local-first bridge choice

Phase 1 uses an in-process transport that imports `mcp_app.tools` from the existing server repo. This keeps local development simple while preserving a transport seam for a real MCP client later.
