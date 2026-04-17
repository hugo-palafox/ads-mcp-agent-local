# Learning Rules

This document explains exactly what the agent can learn, what it rejects, and how to inspect learning history.

## Allowed learning categories

The agent only accepts these three learning types:

1. Tag behavior mappings
- Shape: `<tag> == <value> means <meaning>`
- Example: `Teach that nMachineState == 2 means faulted`
- Purpose: interpret machine state from `read_memory` outputs.

2. Response behavior preferences
- Shape: style/format instruction only.
- Example: `Teach response behavior: be concise and use bullet points`
- Purpose: adjust response style, not tool safety.

3. Tag aliases
- Shape: natural language alias mapping to a tag/memory field.
- Example: `Learn alias Good Parts for Globals.nGood`
- Purpose: let users reference machine fields with friendly names.

## Rejected learning types

The agent rejects learning requests outside those two categories, including:

- Safety-bypass/control instructions
- Write-confirmation bypass instructions
- Credentials/secrets related instructions
- Generic non-learning requests

Rejected events are still recorded in the learning registry with `status: "rejected"` and a stable `reason_code`.

## Reason codes

Common `reason_code` values:

- `accepted_tag_behavior`
- `accepted_response_behavior`
- `accepted_tag_alias`
- `unsafe_response_behavior_content`
- `response_behavior_instruction_too_long`
- `empty_response_behavior_instruction`
- `tag_alias_invalid_format`
- `tag_alias_invalid_target_format`
- `tag_alias_unknown_target`
- `tag_alias_ambiguous_target`
- `tag_alias_conflict`
- `unsupported_learning_intent`

## How to query learning info

Show rules directly in chat:

```powershell
ads-agent chat --machine Machine1 --prompt "Show learning rules"
```

Show current registry JSON:

```powershell
ads-agent chat --machine Machine1 --prompt "Show learning registry json"
```

Show learned aliases:

```powershell
ads-agent chat --machine Machine1 --prompt "Show learning aliases"
```

Show learned mappings:

```powershell
ads-agent chat --machine Machine1 --prompt "Show learned state mappings"
```

Timing note:

- `chat` prints response timing by default; add `--hide-timing` to suppress timing output.

## Registry structure (high level)

Machine registry JSON includes:

- `machine_id`
- `state_rules`
- `response_rules`
- `tag_alias_rules`
- `learning_registry`
- `registry_metadata`

Each learning event contains:

- `timestamp_utc`
- `category`
- `status`
- `source_prompt`
- `source_prompt_excerpt`
- `detail`
- `reason_code`
- `metadata`
