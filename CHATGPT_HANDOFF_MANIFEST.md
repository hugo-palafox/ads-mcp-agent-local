# ChatGPT Handoff Manifest

## 1) Project Identity

- Name: `ads-mcp-agent-local`
- Purpose: Local-first orchestration agent that connects an OpenAI-compatible model endpoint (Ollama by default) to `ads-mcp-server` tools for safe industrial read/write Q&A.
- Primary runtime entrypoint: `ads-agent` CLI (`python -m cli.main` fallback always works).

## 2) Current Architecture

- CLI: `cli/main.py`
- Orchestrator loop: `agent/orchestrator.py`
- Prompt policy: `agent/prompts.py`
- Tool definitions/validation: `agent/tool_registry.py`
- Tool execution: `agent/tool_executor.py`
- LLM API client: `llm/openai_compat.py`, `llm/client.py`
- MCP bridge: `mcp_bridge/transport.py`, `mcp_bridge/client.py`, `mcp_bridge/ads_tools.py`

## 3) Critical Runtime Assumptions

- Agent reads machine/memory data from the repo path in `ADS_AGENT_MCP_SERVER_REPO`.
- Current expected server repo path:
  - `C:\Users\hugod\source\repos\ads-mcp-server`
- Ollama base URL default:
  - `http://localhost:11434/v1`
- Default model in code:
  - `qwen3:8b`

## 4) What Was Fixed Recently

- Added direct model check command:
  - `ads-agent model-chat --prompt "..."`
- Improved fallback answers when model returns empty text after successful tool execution.
- Added compatibility shim in `cli/main.py` so `ads-mcp` entrypoint collisions (`cli.main`) do not break when called from this repo.
- Set git identity locally/globally for this machine:
  - Name: `Hugo Palafox`
  - Email: `hugodavidx@gmail.com`

## 5) Current Known-Working Flow

1. Ensure `ads-mcp-server` has discovered tags and memory tags for `Machine1`.
2. Run:
   - `ads-agent diagnose-model`
   - `ads-agent diagnose-mcp --machine Machine1`
   - `ads-agent chat --machine Machine1 --prompt "What is the machine state?" --show-tool-trace`
3. For write demo:
   - `ads-agent chat --machine Machine1 --prompt "Set Globals.bStartButton to true" --show-tool-trace`
   - Confirm with `y` when prompted.

## 6) Write Guardrails (Important)

- Machine config must allow writes:
  - In `data/machines/Machine1.json`, set `mcp.read_only` to `false`.
- Server-side write guardrail currently allows only tag names containing `"button"`.
- Write flow is two-step:
  - Model calls `request_tag_write`.
  - Runtime asks user confirmation and then calls `confirm_tag_write`.

## 7) Common Failure Causes

- `No answer returned by the model`:
  - Model returned empty final content after tool calls.
  - Fallback logic improved, but model behavior can still vary.
- Empty memory in agent (`{}`):
  - Wrong `ADS_AGENT_MCP_SERVER_REPO` path or missing memory tags in server repo.
- `ads-agent` / `ads-mcp` command not recognized:
  - Missing user Scripts path in `PATH`.
  - `python -m cli.main ...` is immediate fallback.

## 8) High-Value Next Improvements

1. Add structured state interpretation layer for `nMachineState` mapping (config-driven enum mapping).
2. Add anti-hallucination output mode for setup/help prompts (strict command whitelist in response templates).
3. Add persistent conversation memory/session option for multi-turn operations.
4. Add explicit `setup-help` CLI command that prints validated local commands only.
5. Add integration test for real write confirmation loop in interactive mode (or pseudo-tty harness).

## 9) Suggested Prompt To Continue In ChatGPT

Use this exact prompt in a fresh ChatGPT session:

```
You are continuing development of ads-mcp-agent-local.

Constraints:
- Keep architecture and command UX stable unless explicitly improving it.
- Prefer minimal, safe changes with tests.
- Do not remove write safety confirmation flow.
- Do not assume cloud endpoints; local Ollama + local ads-mcp-server are primary.

Current environment:
- Agent repo: C:\Users\hugod\source\repos\ads-mcp-agent-local
- Server repo: C:\Users\hugod\source\repos\ads-mcp-server
- Machine: Machine1

First tasks:
1) Audit prompts and fallback behavior for empty model outputs after tools.
2) Add a robust machine-state interpretation helper for Globals.nMachineState.
3) Add/update tests and docs for any behavior changes.
```

## 10) Quick Verification Commands

```powershell
python -m pytest -q
python -m cli.main model-chat --prompt "Reply with one short sentence."
python -m cli.main diagnose-mcp --machine Machine1
python -m cli.main chat --machine Machine1 --prompt "Read all memory tags and summarize them" --show-tool-trace
```

