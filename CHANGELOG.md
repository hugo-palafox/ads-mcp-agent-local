# CHANGELOG

## 0.1.1 - 2026-03-06

### Added
- Added root `USAGE.md` with detailed Windows PowerShell setup, install, test, diagnostics, chat usage, environment variable configuration, and troubleshooting steps.

### Changed
- Updated `README.md` to reference the new `USAGE.md` guide.

### Fixed
- Fixed in-process MCP tool execution to run within the configured `ads-mcp-server` repository directory, preventing relative path failures such as missing `data\\machines\\M1.json` when launched from another working directory.
- Fixed OpenAI-compatible follow-up tool-call message formatting by serializing `tool_calls[].function.arguments` as JSON strings, avoiding Ollama/OpenAI-compat HTTP 400 contract errors.
- Fixed Windows configuration fallback for `ADS_AGENT_MCP_SERVER_REPO` by adding an OS-aware default and normalization for `/mnt/<drive>/...` style values.

### Removed
- N/A

### Notes
- Usage instructions now include direct fallback commands (`python -m cli.main ...`) when the `ads-agent` script is not yet available on PATH.

## 0.1.0 - 2026-03-06

### Added
- Initial `ads-mcp-agent-local` project skeleton.
- OpenAI-compatible LLM client layer for local Ollama and future enterprise endpoints.
- MCP bridge abstractions, phase 1 tool registry, tool executor, orchestrator loop, and CLI.
- Unit tests, integration tests, QA docs, architecture docs, and code-flow docs.

### Changed
- N/A

### Fixed
- N/A

### Removed
- N/A

### Notes
- Phase 1 uses an in-process transport into `ads-mcp-server` to keep local testing reliable while preserving a future MCP transport seam.
