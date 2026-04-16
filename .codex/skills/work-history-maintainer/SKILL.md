---
name: work-history-maintainer
description: Keep a running planning and implementation history for this repo. Use when a work session completes or materially changes direction, and append a session entry to docs/history/session-log.md.
---

# Work History Maintainer

Append one entry per work session to `docs/history/session-log.md`.

## Required workflow
1. Read the latest section in `docs/history/session-log.md`.
2. Append a new session entry at the top of the log (newest first).
3. Include concise facts only from completed work in the session.

## Entry template
Use this exact structure:

```markdown
## <YYYY-MM-DD HH:MM TZ> - <short title>
- Request: <what the user asked>
- Plan: <implementation direction chosen>
- Implemented: <core code/doc changes>
- Verification: <tests/checks run and outcomes>
- Risks/Follow-ups: <remaining risks or next actions>
```

## Editing rules
- Never rewrite prior entries except to fix obvious formatting defects.
- Keep each bullet single-line and actionable.
- Include test outcomes with pass/fail and scope.

## Output requirements
- Apply edits directly.
- Mention the new entry timestamp/title in the final response.
