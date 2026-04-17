# ads-mcp-agent-local

Local-first orchestration agent that connects an OpenAI-compatible model endpoint to the existing `ads-mcp-server` tool surface for safe industrial Q&A with a guarded two-step write flow.

## Phase 2 goals

- OpenAI-compatible model access, with Ollama as the first target
- Read/write tool calling through the existing `ads-mcp-server` with explicit runtime confirmation for writes
- CLI-first local testing and experimentation
- Strong unit and integration test coverage
- QA and handoff documentation for engineering teams

## Project layout

- `agent/`: orchestration loop, prompt rules, conversation state, tool registry, tool executor
- `llm/`: OpenAI-compatible request and response handling
- `mcp_bridge/`: ADS MCP bridge abstractions and local transport
- `cli/`: local CLI entrypoints
- `config/`: defaults and environment-driven settings
- `tests/`: unit tests, integration tests, fixtures
- `docs/`: architecture, flows, QA, and operational docs

## Configuration

Environment variables:

- `ADS_AGENT_MODEL_BASE_URL` default `http://localhost:11434/v1`
- `ADS_AGENT_MODEL_API_KEY` default `ollama`
- `ADS_AGENT_MODEL_NAME` default `gemma4:e4b`
- `ADS_AGENT_MODEL_THINKING` default unset/provider default
- `ADS_AGENT_TIMEOUT_SECONDS` default `90`
- `ADS_AGENT_TEMPERATURE` default `0.1`
- `ADS_AGENT_MAX_TOKENS` default `800`
- `ADS_AGENT_MAX_TOOL_STEPS` default `4`
- `ADS_AGENT_MAX_TOOL_FAILURES` default `2`
- `ADS_AGENT_DEBUG` default `false`
- `ADS_AGENT_MCP_SERVER_REPO` default `/mnt/c/Users/hugod/source/repos/ads-mcp-server`
- `ADS_AGENT_MCP_TRANSPORT` default `inprocess`
- `ADS_AGENT_TEACHING_STORE_DIR` default `~/.ads-agent/teachings`

## Local usage

```bash
pip install -e .[dev]
ads-agent tools list
ads-agent diagnose-model
ads-agent diagnose-model --timeout-seconds 120
ads-agent diagnose-model --model gemma4:e4b --no-think

ads-agent model-chat --prompt "Reply with one sentence"
ads-agent model-chat --model gemma4:e4b --no-think --prompt "Reply with one sentence"

ads-agent diagnose-mcp --machine Machine1
ads-agent chat --machine Machine1 --prompt "What is the machine state?"
ads-agent chat --machine Machine1 --prompt "Teach that bRun true means running, and nMachineState == 1 is running, ==2 faulted, ==3 stopped"
ads-agent chat --machine Machine1 --prompt "Teach response behavior: be concise and use bullet points"
ads-agent chat --machine Machine1 --prompt "Learn alias Good Parts for Globals.nGood"
ads-agent chat --machine Machine1 --prompt "Show learned state mappings"
ads-agent chat --machine Machine1 --prompt "Show learning aliases"
ads-agent chat --machine Machine1 --prompt "Show learning registry json"
ads-agent learning reset --machine Machine1
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --timeout-seconds 120
ads-agent chat --machine Machine1 --prompt "Read all memory tags and summarize them" --show-tool-trace
ads-agent chat --machine Machine1 --prompt "Set Globals.bStartButton to true" --show-tool-trace
```

Timing is printed by default after each `chat` and `model-chat` response. Use `--hide-timing` to suppress it.
Model thinking is provider-default unless configured. Use `ADS_AGENT_MODEL_THINKING=true|false` for a session default, or `--think` / `--no-think` on `chat`, `model-chat`, and `diagnose-model` to override per command.

For full setup and run instructions, see `USAGE.md`.
For learning feature rules and examples, see [`docs/learning-rules.md`](docs/learning-rules.md).
For an automated end-user smoke run with a saved transcript report, use `python scripts/feature_smoke_test.py`.

## Project-local maintainer skills

This repository includes project-local skills in `.codex/skills` and discovery rules in `AGENTS.md`:

- `readme-maintainer`
- `usage-maintainer`
- `changelog-maintainer`
- `work-history-maintainer`

These skills are implementation-first and directly update their target files.

## Design notes

- The bridge keeps `ads-mcp-server` isolated behind `AdsMcpClient` and `AdsToolBridge`.
- The model can only call `request_tag_write`; the runtime performs `confirm_tag_write` after explicit user input.
- Non-interactive sessions auto-cancel pending write requests for safety.
- Local tool-enabled model calls can take longer than trivial diagnostics, so the CLI supports `--timeout-seconds` and now defaults to 90 seconds.
- Thinking-capable models can be forced on or off with the generic `think` request setting when the endpoint supports it.
- Phase 2 still uses an in-process transport for local reliability and simple testing.
- The rest of the agent is transport-agnostic and can later move to a networked MCP client without rewriting the tool loop.
- Learning guardrail: the agent only learns safe `tag behavior` mappings, `response behavior` preferences, and `tag aliases`, with accepted/rejected learning recorded in machine JSON.

## Quick demo commands

Fast path:

```powershell
ads-agent chat --machine Machine1 --prompt "Read all memory tags and summarize them" --show-tool-trace --tool-trace-format pretty
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --show-tool-trace --tool-trace-format pretty
ads-agent chat --machine Machine1 --prompt "Set Globals.bStartButton to true" --show-tool-trace
ads-agent chat --machine Machine1 --prompt "Set Globals.bStopButton to true" --show-tool-trace
ads-agent chat --machine Machine1 --prompt "Show learning rules"
python scripts/feature_smoke_test.py
```

## Feature demo commands

Use this ordered command list to showcase the full agent capability from diagnostics through reads, learning, guarded writes, and automated smoke coverage:

```powershell
ads-agent diagnose-model --model gemma4:e4b --no-think
ads-agent model-chat --model gemma4:e4b --no-think --prompt "Reply with one sentence describing your role."
ads-agent diagnose-mcp --machine Machine1

ads-agent chat --machine Machine1 --model gemma4:e4b --no-think --prompt "What is the machine state?" --show-tool-trace --tool-trace-format pretty
ads-agent chat --machine Machine1 --model gemma4:e4b --no-think --prompt "Read all memory tags and summarize them" --show-tool-trace --tool-trace-format pretty
ads-agent chat --machine Machine1 --model gemma4:e4b --no-think --prompt "Read Globals.bRun" --show-tool-trace

ads-agent chat --machine Machine1 --prompt "Teach that nMachineState == 2 means faulted"
ads-agent chat --machine Machine1 --prompt "Teach response behavior: be concise and use bullet points"
ads-agent chat --machine Machine1 --prompt "Learn alias Good Parts for Globals.nGood"
ads-agent chat --machine Machine1 --prompt "Show learning aliases"
ads-agent chat --machine Machine1 --prompt "Show learning registry json"
ads-agent chat --machine Machine1 --prompt "Show learning rules"
ads-agent learning reset --machine Machine1

ads-agent chat --machine Machine1 --model gemma4:e4b --no-think --prompt "Set Globals.bStartButton to true" --show-tool-trace
ads-agent chat --machine Machine1 --model gemma4:e4b --no-think --prompt "Set Globals.bStopButton to true" --show-tool-trace

python scripts/feature_smoke_test.py --model gemma4:e4b --machine Machine1
```

Demo flow:

- The first three commands prove model and MCP connectivity.
- The next three show broad reads, summarized reads, and specific-tag reads with tool trace visibility.
- The learning commands show safe teach/retrieve behavior for state mappings, response preferences, aliases, and registry inspection.
- `ads-agent learning reset --machine Machine1` clears only the agent's learned memory for that machine; it does not reset PLC tags or delete machine configuration.
- The write commands demonstrate the guarded confirmation workflow. In a non-interactive shell they auto-cancel safely.
- The smoke script runs a transcripted end-user feature pass and saves a report under `artifacts/smoke-tests/`.
