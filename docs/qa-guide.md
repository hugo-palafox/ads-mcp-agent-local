# QA Guide

## QA goals

Verify that answers are grounded in tool output and that prompt intent maps to the right tool behavior.

## Checklist

- The selected tool matches the request intent.
- The agent does not invent tag names.
- The agent does not invent tag values.
- Broad prompts prefer `read_memory`.
- Specific tag prompts prefer `read_tag`.
- Write prompts use `request_tag_write` before any write claim.
- Pending write requests require explicit confirmation before a `written` claim.
- Cancelled, expired, and rejected confirmations are reported exactly as returned.
- Final answers are traceable to returned tool payloads.
- MCP errors are surfaced without claiming success.
- No-tool responses remain explicit about uncertainty.
- Repeated prompts do not cause unsafe write claims.

## Suggested validations

Automated baseline:

- Run `python scripts/feature_smoke_test.py` to execute the documented end-user flow and save a transcript report.

1. Run `ads-agent chat --machine M1 --prompt "What is the machine state?" --show-tool-trace`.
2. Confirm the first tool is `read_memory` for broad state or summary prompts.
3. Run `ads-agent chat --machine M1 --prompt "Read Globals.bRun" --show-tool-trace`.
4. Confirm the tool is `read_tag` and the answer only references returned values.
5. Force an MCP failure and verify the final answer says the read could not be verified.
6. Ask for a nonexistent tag and verify the answer reports missing data rather than inventing a value.
7. Run `ads-agent chat --machine M1 --prompt "Set Globals.bStartButton to true" --show-tool-trace` and deny confirmation. Verify final status is cancelled.
8. Run the same write prompt and approve confirmation. Verify final status is written.
9. Run write prompt in non-interactive mode and verify pending requests are auto-cancelled.

## Hallucination checks

- Compare every value in the final answer to the tool trace.
- Compare every mentioned tag name to `list_memory_tags` or the explicit `read_tag` request.
- Reject any output that implies a write unless a `confirm_tag_write` result reports `status: "written"`.
