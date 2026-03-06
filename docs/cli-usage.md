# CLI Usage

## Commands

```bash
ads-agent tools list
ads-agent diagnose-model
ads-agent diagnose-mcp --machine M1
ads-agent chat --machine M1 --prompt "What is the machine state?"
ads-agent chat --machine M1 --prompt "Read all memory tags and summarize them" --show-tool-trace
ads-agent chat --machine M1 --prompt "Is the machine running or faulted?" --debug
```

## Flags

- `--debug`: also prints tool trace output
- `--show-tool-trace`: prints structured tool call results
- `--max-tool-steps`: overrides loop limit for the current command
- `--model`: overrides `ADS_AGENT_MODEL_NAME`
- `--base-url`: overrides `ADS_AGENT_MODEL_BASE_URL`

## Output interpretation

- Standard output prints the final answer first.
- Tool traces are emitted as JSON objects with `ok`, `tool_name`, `arguments`, and either `result` or `error`.
