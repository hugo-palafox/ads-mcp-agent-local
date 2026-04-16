# CHANGELOG

## 0.3.1 - 2026-04-16

### Added
- Added `*.egg-info/`, build, and dist ignore rules so generated packaging artifacts stay out of source control.
- Added explicit learning-query examples (`Show learning rules`, `Show learning registry json`) in `docs/cli-usage.md`.

### Changed
- Changed README quick demo commands to a single fenced block and removed redundant `--show-timing` flags from default timing examples.
- Changed usage/docs wording to consistently describe timing as default-on with `--hide-timing` override.

### Fixed
- Fixed repository hygiene by removing tracked `ads_mcp_agent_local.egg-info/*` files from git while preserving local generation behavior.
- Fixed cross-document consistency across `README.md`, `USAGE.md`, `docs/cli-usage.md`, and `docs/learning-rules.md`.

### Removed
- Removed tracked `ads_mcp_agent_local.egg-info/*` metadata files from the repository index.

### Notes
- This is a cleanup-only patch release; no runtime behavior changes were introduced.

## 0.3.0 - 2026-04-16

### Added
- Added structured learning registry metadata (`registry_metadata`) and per-event diagnostics (`reason_code`, `source_prompt_excerpt`, `metadata`) while preserving existing registry keys.
- Added four project-local maintainer skills under `.codex/skills`: `readme-maintainer`, `usage-maintainer`, `changelog-maintainer`, and `work-history-maintainer`.
- Added repository skill discovery and trigger guidance via `AGENTS.md`.
- Added persistent implementation session history file: `docs/history/session-log.md`.

### Changed
- Changed teaching-path responses to a standardized learning summary format with accepted/rejected counts.
- Changed rejection handling to include stable reason codes and clearer user-facing rejection messages.
- Changed learning query classifiers to reduce false interception of non-learning prompts.

### Fixed
- Fixed learning shortcut false positives where generic prompts about rules could bypass normal model/orchestration flow.
- Fixed registry event normalization so legacy event shapes remain readable while new metadata is captured for QA/debugging.

### Removed
- N/A

### Notes
- Learning categories remain constrained to `tag_behavior` and `response_behavior`.
- Maintainer skills are implementation-first and directly edit target docs/history files.

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
