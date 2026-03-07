# CLI Usage

## Commands

```bash
ads-agent tools list
ads-agent diagnose-model
ads-agent diagnose-model --timeout-seconds 120
ads-agent model-chat --prompt "Reply with one short sentence"
ads-agent model-chat --prompt "Reply with one short sentence" --show-timing
ads-agent diagnose-mcp --machine Machine1
ads-agent chat --machine Machine1 --prompt "What is the machine state?"
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --show-timing
ads-agent chat --machine Machine1 --prompt "What is the machine state?" --timeout-seconds 120
ads-agent chat --machine Machine1 --prompt "Read all memory tags and summarize them" --show-tool-trace
ads-agent chat --machine Machine1 --prompt "Read all memory tags and summarize them" --show-tool-trace --tool-trace-format pretty
ads-agent chat --machine Machine1 --prompt "Start Machine" --show-tool-trace --tool-trace-format pretty --show-timing
ads-agent chat --machine Machine1 --prompt "Stop Machine" --show-tool-trace --tool-trace-format pretty --show-timing
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
- `--show-timing`: prints end-to-end response time in seconds

## Output interpretation

- Standard output prints the final answer first.
- Tool traces are emitted as JSON objects with `ok`, `tool_name`, `arguments`, and either `result` or `error`.
- Runtime failures such as model timeouts are printed as `ERROR: ...` on stderr without a Python traceback.
