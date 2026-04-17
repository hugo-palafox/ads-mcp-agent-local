# CLI Usage

## Commands

```bash
ads-agent tools list
ads-agent learning reset --machine Machine1
ads-agent diagnose-model
ads-agent diagnose-model --timeout-seconds 120
ads-agent diagnose-model --no-think
ads-agent model-chat --prompt "Reply with one short sentence"
ads-agent model-chat --model gemma4:e4b --no-think --prompt "Reply with one short sentence"
ads-agent diagnose-mcp --machine Machine1
ads-agent chat --machine Machine1 --prompt "What is the machine state?"
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --timeout-seconds 120
ads-agent chat --machine Machine1 --prompt "list tags memory" --model gemma4:e4b --no-think --timeout-seconds 120
ads-agent chat --machine Machine1 --prompt "Read all memory tags and summarize them" --show-tool-trace
ads-agent chat --machine Machine1 --prompt "Read all memory tags and summarize them" --show-tool-trace --tool-trace-format pretty
ads-agent chat --machine Machine1 --prompt "Show learning rules"
ads-agent chat --machine Machine1 --prompt "Show learning registry json"
ads-agent chat --machine Machine1 --prompt "Set Globals.bStartButton to true" --show-tool-trace
ads-agent chat --machine Machine1 --prompt "Set Globals.bStopButton to true" --show-tool-trace
ads-agent chat --machine Machine1 --prompt "Is the machine running or faulted?" --debug
```

## Flags

- `--debug`: also prints tool trace output
- `--show-tool-trace`: prints structured tool call results
- `--tool-trace-format`: `json` (default) or `pretty` for presenter-friendly output
- `--max-tool-steps`: overrides loop limit for the current command
- `--model`: overrides `ADS_AGENT_MODEL_NAME`
- `--base-url`: overrides `ADS_AGENT_MODEL_BASE_URL`
- `--timeout-seconds`: overrides `ADS_AGENT_TIMEOUT_SECONDS` for the current command
- `--think` / `--no-think`: override `ADS_AGENT_MODEL_THINKING` for the current command
- `--show-timing`: explicitly keeps timing output on (default behavior)
- `--hide-timing`: hides end-to-end response time output

## Output interpretation

- Standard output prints the final answer first.
- Response timing is printed by default for `chat` and `model-chat`; use `--hide-timing` to suppress it.
- Thinking is provider-default unless configured; `think` is only sent when set via env or CLI.
- Tool traces are emitted as JSON objects with `ok`, `tool_name`, `arguments`, and either `result` or `error`.
- Runtime failures such as model timeouts are printed as `ERROR: ...` on stderr without a Python traceback.
- `learning reset --machine <id>` clears only the stored learned memory JSON for that machine; it does not modify PLC tags or ads-mcp-server machine data.
