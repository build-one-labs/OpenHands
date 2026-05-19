# Environment Skills

Skills in this directory are loaded into a conversation **only when it is
connected to an environment** (a running sandbox/runtime).

They are merged in by the V1 app-server skill loader —
`load_environment_skills()` in
`openhands/app_server/app_conversation/skill_loader.py`, called from
`AppConversationServiceBase.load_and_merge_all_skills()`.

This is deliberately separate from the top-level `skills/` directory, whose
skills are loaded unconditionally as global microagents by the V0 system
(`openhands/memory/memory.py`). Put a skill here when it should apply *only*
to environment-connected conversations.

## Adding a skill

Drop a markdown file into this directory. Two formats are supported:

- **Legacy format** — a `*.md` file with frontmatter (`name`, `type`,
  `triggers`, ...). A keyword `triggers` list auto-injects the skill content
  when one of the trigger words appears in the conversation.
- **AgentSkills format** — a `skill-name/SKILL.md` directory.

A `README.md` placed here is ignored by the loader, so this file is safe.

## Precedence

Environment skills are merged at the **lowest** precedence: a public, user,
organization, or project skill with the same `name` overrides the environment
skill of that name.
