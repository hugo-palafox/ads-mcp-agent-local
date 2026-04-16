---
name: changelog-maintainer
description: Maintain CHANGELOG.md entries for implemented work. Use when features, fixes, behavior changes, or documentation-impacting updates are shipped and require a versioned changelog record.
---

# Changelog Maintainer

Append/update `CHANGELOG.md` with accurate versioned release notes.

## Required workflow
1. Inspect implemented changes and tests.
2. Add or update the top release entry using existing format:
   - `## <version> - <YYYY-MM-DD>`
   - Added / Changed / Fixed / Removed / Notes
3. Keep entries behavior-focused and user-relevant.
4. Include notable safety, compatibility, and testing notes when applicable.

## Editing rules
- Preserve historical entries exactly.
- Do not invent versions already used elsewhere.
- Keep bullet wording concrete and verifiable from code/tests.
- Keep each bullet scoped to a single change.

## Output requirements
- Apply edits directly.
- Report the updated version header and key bullets added.
