# AGENTS.md instructions for this repository

## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of project-local skills that can be used.

### Available skills
- readme-maintainer: Maintain `README.md` command examples and behavior notes so they match current runtime behavior. (file: .codex/skills/readme-maintainer/SKILL.md)
- usage-maintainer: Maintain `USAGE.md` command/flag sections and examples to match implemented CLI defaults and behavior. (file: .codex/skills/usage-maintainer/SKILL.md)
- changelog-maintainer: Maintain `CHANGELOG.md` with versioned Added/Changed/Fixed/Removed entries for implemented work. (file: .codex/skills/changelog-maintainer/SKILL.md)
- work-history-maintainer: Append planning/implementation session records to `docs/history/session-log.md` to keep a running execution history. (file: .codex/skills/work-history-maintainer/SKILL.md)

### How to use skills
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the request clearly matches one of the descriptions above, use that skill for that turn.
- Multiple skills: If more than one skill applies, execute them in this order unless the user requests otherwise:
  1) `readme-maintainer` / `usage-maintainer`
  2) `changelog-maintainer`
  3) `work-history-maintainer`
- Execution mode: These project-maintainer skills are implementation-first and should directly update files.
- Validation: After substantial edits, run relevant tests/checks and include concise verification notes in the response.
