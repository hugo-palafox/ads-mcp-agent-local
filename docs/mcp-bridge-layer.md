# MCP Bridge Layer

The MCP bridge isolates `ads-mcp-server` from the orchestration code.

## Exposed Phase 1 tools

- `list_groups`
- `list_memory_tags`
- `read_tag`
- `read_memory`

## Internal structure

- `AdsMcpClient` is the generic invocation surface.
- `AdsToolBridge` provides typed wrapper methods for each ADS tool.
- `InProcessAdsMcpTransport` loads the existing server repo and calls its published tool functions.

## Why this separation matters

- The LLM layer never imports or understands server internals.
- The tool executor stays deterministic and easy to mock.
- The transport can later change to a true MCP network client without rewriting the registry or orchestrator.
