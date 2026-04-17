# LLM Layer

The LLM layer wraps an OpenAI-compatible chat completion endpoint.

## Current target

- Base URL: `http://localhost:11434/v1`
- API key: `ollama`
- Model: `qwen3:8b`

## Responsibilities

- Build chat completion payloads with messages and tool schemas.
- Parse OpenAI-style tool calls from `choices[0].message.tool_calls`.
- Raise deterministic errors for timeouts, malformed tool arguments, and empty responses.

## Future migration

The client is configured entirely by environment values. Moving from local Ollama to an enterprise endpoint should only require changing:

- `ADS_AGENT_MODEL_BASE_URL`
- `ADS_AGENT_MODEL_API_KEY`
- `ADS_AGENT_MODEL_NAME`
