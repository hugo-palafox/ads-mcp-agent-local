# CHANGELOG

## 0.2.0 - 2026-03-06

### Added
- Added model-exposed `request_tag_write` to the tool registry and MCP bridge wrappers.
- Added orchestrator-controlled write confirmation checkpoint that performs `confirm_tag_write` only after explicit user approval.
- Added non-interactive auto-cancel behavior for pending write requests.
- Added unit and integration coverage for request/confirm write flow, including approve, deny, expired, and auto-cancel scenarios.
- Added dedicated implementation handoff document: `HANDOFF_WRITE_FLOW_0.2.0.md`.

### Changed
- Changed prompt policy from strict read-only language to a write-safe two-step contract that requires confirmation evidence before any write claim.
- Changed docs across README, usage, architecture, flow, bridge, and QA to reflect the guarded write workflow.

### Fixed
- Fixed tool argument validation by enforcing declared schema types, including scalar-only validation for `request_tag_write.value`.

### Removed
- N/A

### Notes
- `confirm_tag_write` is orchestration-controlled and intentionally not exposed as a model-callable tool.

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
