---
name: usage-maintainer
description: Maintain USAGE.md as the operational runbook for this repo. Use when CLI flags, defaults, workflows, troubleshooting steps, or examples change and USAGE.md must be synchronized.
---

# USAGE Maintainer

Update `USAGE.md` directly to match the implemented CLI and runtime behavior.

## Required workflow
1. Read `USAGE.md` plus relevant CLI/config/runtime code.
2. Update command examples, flags, defaults, and troubleshooting sections as needed.
3. Ensure examples reflect current default behavior first, then optional overrides.
4. Keep explicit PowerShell-friendly commands.
5. Validate at least one representative command path when possible.

## Editing rules
- Keep section numbering intact unless a strong reason exists.
- Keep examples copy-pastable.
- Do not leave stale flags/default values in alternate sections.
- Keep descriptions factual and tied to code behavior.

## Output requirements
- Apply edits directly.
- Summarize changed sections and mention verification performed.
