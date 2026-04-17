# Deployment Guide

This guide explains how to move `ads-mcp-agent-local` to another Windows computer, install it, and run it.

## 1. What You Need on the Target Computer

- Windows with PowerShell
- Python 3.10 or newer available as `python` or `py`
- Git
- Ollama installed locally
- Access to the `ads-mcp-server` repository
- Access to this `ads-mcp-agent-local` repository

## 2. Copy or Clone the Repositories

You need both repositories on the new computer because this agent currently uses an in-process bridge to the server code.

Recommended layout:

```text
C:\Users\<your-user>\source\repos\ads-mcp-server
C:\Users\<your-user>\source\repos\ads-mcp-agent-local
```

Clone example:

```powershell
cd C:\Users\<your-user>\source\repos
git clone <ads-mcp-server-repo-url> ads-mcp-server
git clone <ads-mcp-agent-local-repo-url> ads-mcp-agent-local
```

If you are copying folders manually instead of cloning, preserve the full project contents for both repos.

## 3. Install Ollama and Pull a Tool-Capable Model

Start Ollama:

```powershell
ollama serve
```

Pull the default model used by this project:

```powershell
ollama pull qwen3:8b
```

Note:

- The main agent model must support tool calling.
- `deepseek-r1:8b` is not suitable as the primary agent model in the current architecture if Ollama reports that it does not support tools.

## 4. Install `ads-mcp-server`

From the server repository:

```powershell
cd C:\Users\<your-user>\source\repos\ads-mcp-server
python -m pip install -e .
```

If the server repo has additional machine data or PLC-specific configuration outside version control, copy that as well before testing.

## 5. Install `ads-mcp-agent-local`

From the agent repository:

```powershell
cd C:\Users\<your-user>\source\repos\ads-mcp-agent-local
python -m pip install -e .[dev]
```

If `ads-agent` is not available immediately after install, restart PowerShell.

## 6. Configure Environment Variables

Set the local model endpoint and the path to `ads-mcp-server`:

```powershell
$env:ADS_AGENT_MODEL_BASE_URL = "http://localhost:11434/v1"
$env:ADS_AGENT_MODEL_API_KEY = "ollama"
$env:ADS_AGENT_MODEL_NAME = "qwen3:8b"
$env:ADS_AGENT_TIMEOUT_SECONDS = "120"
$env:ADS_AGENT_MCP_SERVER_REPO = "C:\Users\<your-user>\source\repos\ads-mcp-server"
```

If you want these to persist across sessions, set them with Windows System Settings or your PowerShell profile instead of only the current shell.

## 7. Validate the Installation

### 7.1 Validate the model endpoint

```powershell
ads-agent diagnose-model --timeout-seconds 120
```

Expected result:

- A JSON response with `"content": "OK"`

### 7.2 Validate MCP bridge access

```powershell
ads-agent diagnose-mcp --machine Machine1
```

Expected result:

- A JSON response showing at least `list_groups` and `list_memory_tags`

### 7.3 Run the automated tests

From the agent repo:

```powershell
python -m pytest -q
```

## 8. First Run Commands

Read-only question:

```powershell
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --timeout-seconds 120
```

Show the tool trace:

```powershell
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --timeout-seconds 120 --show-tool-trace
```

Write-flow example:

```powershell
ads-agent chat --machine Machine1 --prompt "Set Globals.bStartButton to true" --timeout-seconds 120 --show-tool-trace
```

Expected write-flow behavior:

- The model requests `request_tag_write`
- The server resolves a full tag name
- The CLI asks for confirmation
- Typing `y` or `yes` approves the write
- Any other response cancels the write

## 9. Fallback Command Style

If the `ads-agent` entrypoint is not available, use module invocation:

```powershell
python -m cli.main diagnose-model --timeout-seconds 120
python -m cli.main diagnose-mcp --machine Machine1
python -m cli.main chat --machine Machine1 --prompt "What is the machine state?" --timeout-seconds 120
```

## 10. Common Deployment Problems

### `ads-agent` is not recognized

- Run `python -m pip install -e .[dev]` from the agent repo
- Restart PowerShell
- Use `python -m cli.main ...` as a fallback

### `ERROR: Model request timed out`

- Increase timeout: `--timeout-seconds 120`
- Or set `$env:ADS_AGENT_TIMEOUT_SECONDS = "120"`
- Confirm Ollama is running

### `ERROR: Model request failed: HTTP 400 ... does not support tools`

- Switch to a tool-capable model
- Verify the model works with OpenAI-style tool calling in Ollama

### MCP import or repo path failures

- Confirm `ADS_AGENT_MCP_SERVER_REPO` points to the correct local server repo
- Confirm `ads-mcp-server` is installed with `python -m pip install -e .`

### PLC or machine data issues

- Confirm the target machine definition files exist in the server repo
- Confirm the new computer has the same machine data and PLC connectivity assumptions as the source machine

## 11. Recommended Transfer Checklist

Before declaring the deployment complete, verify all of the following:

- Ollama is installed and running
- A tool-capable model is pulled locally
- `ads-mcp-server` is present and installed
- `ads-mcp-agent-local` is present and installed
- `ADS_AGENT_MCP_SERVER_REPO` points to the correct server path
- `ads-agent diagnose-model` succeeds
- `ads-agent diagnose-mcp --machine Machine1` succeeds
- `ads-agent chat --machine Machine1 --prompt "What is the machine state?" --timeout-seconds 120` succeeds
