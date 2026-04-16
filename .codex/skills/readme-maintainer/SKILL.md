---
name: readme-maintainer
description: Maintain README.md accuracy for this repo. Use when behavior, defaults, CLI examples, or workflow guidance changes and README.md must be updated immediately to match implementation.
---

# README Maintainer

Update `README.md` directly when implementation changes affect documented behavior.

## Required workflow
1. Read current `README.md` and the changed implementation files.
2. Update only sections impacted by behavior/config/command changes.
3. Keep examples runnable on Windows PowerShell.
4. Keep wording concise and implementation-accurate.
5. Run targeted verification commands when practical and reflect actual outcomes.

## Editing rules
- Prefer additive edits over large rewrites.
- Keep command examples aligned with current defaults and flags.
- Avoid speculative statements; document only implemented behavior.
- Preserve existing tone and section structure unless a mismatch requires restructuring.

## Output requirements
- Apply edits directly (no proposal-only mode).
- In the final response, summarize which README sections changed and why.
