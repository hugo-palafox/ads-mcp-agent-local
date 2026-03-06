# Usage Guide

This guide explains exactly how to run `ads-mcp-agent-local` on Windows PowerShell.

## 1. Prerequisites

- Windows Python available as `python` or `py`
- `ads-mcp-server` repo present at:
  - `C:\Users\hugod\source\repos\ads-mcp-server`
- Ollama installed locally (for phase 1 model target)
- Model pulled in Ollama: `qwen3:8b`

## 2. Start Required Services

### 2.1 Ollama

Open a terminal and run:

```powershell
ollama serve
```

In another terminal:

```powershell
ollama pull qwen3:8b
```

### 2.2 ads-mcp-server

From the server repo:

```powershell
cd C:\Users\hugod\source\repos\ads-mcp-server
python -m pip install -e .
```

Note: this agent currently uses an in-process bridge to the server tool module, so the server repo must exist at the configured path.

## 3. Install This Project

```powershell
cd C:\Users\hugod\source\repos\ads-mcp-agent-local
python -m pip install -e .[dev]
```

If `ads-agent` is not found after install, restart PowerShell.

## 4. Run Tests

From project root:

```powershell
python -m pytest -q
```

Alternative explicit path form:

```powershell
python -m pytest -q C:\Users\hugod\source\repos\ads-mcp-agent-local
```

## 5. Default Runtime Configuration

The project reads these environment variables:

- `ADS_AGENT_MODEL_BASE_URL` default `http://localhost:11434/v1`
- `ADS_AGENT_MODEL_API_KEY` default `ollama`
- `ADS_AGENT_MODEL_NAME` default `qwen3:8b`
- `ADS_AGENT_TIMEOUT_SECONDS` default `90`
- `ADS_AGENT_TEMPERATURE` default `0.1`
- `ADS_AGENT_MAX_TOKENS` default `800`
- `ADS_AGENT_MAX_TOOL_STEPS` default `4`
- `ADS_AGENT_MAX_TOOL_FAILURES` default `2`
- `ADS_AGENT_DEBUG` default `false`
- `ADS_AGENT_MCP_SERVER_REPO` default `/mnt/c/Users/hugod/source/repos/ads-mcp-server`
- `ADS_AGENT_MCP_TRANSPORT` default `inprocess`

## 6. Set Environment Variables in PowerShell

Recommended for Windows path consistency:

```powershell
$env:ADS_AGENT_MODEL_BASE_URL = "http://localhost:11434/v1"
$env:ADS_AGENT_MODEL_API_KEY = "ollama"
$env:ADS_AGENT_MODEL_NAME = "qwen3:8b"
$env:ADS_AGENT_MCP_SERVER_REPO = "C:\Users\hugod\source\repos\ads-mcp-server"
```

## 7. Validate Dependencies

### 7.1 Model connectivity

```powershell
ads-agent diagnose-model
ads-agent model-chat --prompt "Reply with one short sentence"
```

If the model is slow under tool use, increase the timeout for the current command:

```powershell
ads-agent diagnose-model --timeout-seconds 120
```

### 7.2 MCP bridge connectivity

```powershell
ads-agent diagnose-mcp --machine Machine1
```

## 8. Chat Commands

### 8.1 Basic machine state

```powershell
ads-agent chat --machine Machine1 --prompt "What is the machine state?"
```

### 8.2 Broad memory summary

```powershell
ads-agent chat --machine Machine1 --prompt "Read all memory tags and summarize them"
```

### 8.3 Specific question

```powershell
ads-agent chat --machine Machine1 --prompt "Is the machine running or faulted?"
```

### 8.4 Show tool trace

```powershell
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --show-tool-trace
```

### 8.5 Debug mode

```powershell
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --debug
```

### 8.6 Override model/base URL/step limit

```powershell
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --model qwen3:8b --base-url http://localhost:11434/v1 --max-tool-steps 6
```

### 8.6.1 Override timeout for slower local models

```powershell
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --timeout-seconds 120
```

### 8.7 Write request with confirmation checkpoint

```powershell
ads-agent chat --machine Machine1 --prompt "Set Main.startButton to true" --show-tool-trace
```

Expected behavior:

- The model calls `request_tag_write`.
- The CLI shows a confirmation prompt with machine, resolved tag, requested value, and request id.
- Enter `y`/`yes` to approve. Any other input cancels.
- The runtime then calls `confirm_tag_write` and the final answer is grounded in the returned status (`written`, `cancelled`, `expired`, or `rejected`).

Non-interactive behavior:

- If stdin/stdout is not interactive, pending writes are auto-cancelled and the CLI prints an auto-cancel notice.

### 8.8 More write examples

Write a boolean button tag:

```powershell
ads-agent chat --machine Machine1 --prompt "Set Main.startButton to true"
```

Cancel a write at the confirmation prompt:

```powershell
ads-agent chat --machine Machine1 --prompt "Set Main.stopButton to false" --show-tool-trace
```

Use a partial tag query and let the server resolve the full tag name:

```powershell
ads-agent chat --machine Machine1 --prompt "Turn the start button on"
```

Use module invocation instead of the installed script:

```powershell
python -m cli.main chat --machine Machine1 --prompt "Set Main.startButton to true" --timeout-seconds 120
```

What you should expect during these write examples:

- The model requests `request_tag_write` first.
- The server resolves one full tag name and returns a pending request id.
- The CLI asks for confirmation before any write is attempted.
- Typing `y` or `yes` approves the write. Any other response cancels it.

## 9. List Exposed Tools

```powershell
ads-agent tools list
```

Model-exposed tools:

- `list_groups`
- `list_memory_tags`
- `read_tag`
- `read_memory`
- `request_tag_write`

Runtime-only tool (not model-exposed):

- `confirm_tag_write`

## 10. Fallback If `ads-agent` Is Not Found

Use module invocation directly:

```powershell
python -m cli.main diagnose-model
python -m cli.main model-chat --prompt "Reply with one short sentence"
python -m cli.main diagnose-mcp --machine Machine1
python -m cli.main chat --machine Machine1 --prompt "What is the machine state?"
```

## 11. Common Errors and Fixes

### `python3` not found on Windows

Use `python` or `py` in PowerShell:

```powershell
py -m pytest -q
```

### `ERROR: file or directory not found: in`

Cause: command typed like `python -m pytest -q in /path`.
Fix: remove `in` and either `cd` first or pass a valid Windows path.

### `ads-agent` command not recognized

- Run: `python -m pip install -e .`
- Restart PowerShell
- Or use `python -m cli.main ...`

### Model timeout or connection errors

- Confirm `ollama serve` is running
- Check `ADS_AGENT_MODEL_BASE_URL`
- Confirm model exists: `ollama list`

### `ERROR: Model request timed out`

- Increase the timeout for the current command: `ads-agent chat --machine Machine1 --prompt "What is the machine state?" --timeout-seconds 120`
- Or set a higher session default: `$env:ADS_AGENT_TIMEOUT_SECONDS = "120"`
- `diagnose-model` can succeed while `chat` still times out because tool-enabled prompts are larger and slower

### MCP import/path errors

- Confirm `ADS_AGENT_MCP_SERVER_REPO` points to the local server repo
- Confirm server repo is installed: `python -m pip install -e .` inside `ads-mcp-server`
