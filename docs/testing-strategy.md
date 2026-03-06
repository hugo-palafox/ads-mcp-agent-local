# Testing Strategy

## Unit tests

Unit tests focus on deterministic behavior inside each layer.

- `test_llm_client.py`: payload construction, parsing, malformed tool calls, timeout handling
- `test_tool_registry.py`: expected tools, argument validation, unknown tool rejection
- `test_tool_executor.py`: success paths, validation failures, MCP errors, structured outputs
- `test_conversation.py`: message ordering and tool message persistence
- `test_ads_tools.py`: bridge method mapping and machine argument handling
- `test_prompt_rules.py`: read-only and anti-hallucination rules

## Integration tests

Integration tests run the orchestrator loop with mocked model responses and mocked MCP results.

- `test_read_memory_flow.py`
- `test_read_tag_flow.py`
- `test_tool_error_flow.py`
- `test_agent_tool_loop.py`
- `test_openai_compat_contract.py`

## Mocking approach

- No live PLC required
- No live ADS connection required
- No live Ollama process required
- Fake model responses live in `tests/fixtures/fake_model_responses.py`
- Fake MCP behavior lives in `tests/fixtures/fake_mcp_client.py`

## Live manual boundaries

Manual testing should be used only for endpoint and server integration validation after the automated suite passes.

Manual cases:

1. Validate model connectivity with `ads-agent diagnose-model`.
2. Validate server connectivity with `ads-agent diagnose-mcp --machine M1`.
3. Ask for machine state and confirm the tool trace uses `read_memory`.
4. Ask for a specific tag and confirm the tool trace uses `read_tag`.
5. Simulate MCP failures and confirm the answer remains grounded.
6. Simulate model timeout and verify the CLI surfaces a deterministic error.
