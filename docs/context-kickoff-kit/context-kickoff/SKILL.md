---
name: context-kickoff
description: Bootstrap project context at the start of a new chat or phase handoff. Use when the user asks to resume work, asks "where are we", asks for current state/next steps, or when you need to quickly load authoritative project docs before making changes. Prioritize discovering and reading canonical status files (for example docs/ENVIRONMENT_INVENTORY.md, docs/IMPLEMENTATION_LOG.md, PRD/phase guides, AGENTS.md) and produce a concise state snapshot plus immediate next actions.
---

# Context Kickoff

## Overview

Establish a reliable starting context for coding work with minimal token usage. Prefer canonical project docs and quick local checks over broad file scanning.

## Workflow

1. Run the kickoff discovery script from this skill, targeting the current repository root:
- Preferred: `"$CODEX_HOME/skills/context-kickoff/scripts/discover_context.sh" "$(pwd)"`
- Fallback if `CODEX_HOME` is unavailable: `~/.codex/skills/context-kickoff/scripts/discover_context.sh "$(pwd)"`
- Final fallback only if script is missing: canonical docs -> `README.md` -> `git status --short --branch`.
2. Read discovered files in this order if present:
- `docs/ENVIRONMENT_INVENTORY.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/README.md`
- `AGENTS.md`
- `README.md`
- PRD/phase guides listed by the discovery script
3. Build a short kickoff snapshot:
- current phase/status
- environment/runtime facts (hosts, ports, active services)
- open blockers/risks
- exact next 1-3 actions
4. Before coding, confirm the task boundary in one sentence and continue.

## Output Contract

Return kickoff output in this shape:

- `Status`: one sentence
- `Facts`: 3-6 bullets grounded in files/commands
- `Risks`: 0-3 bullets
- `Next`: numbered list (1-3 concrete actions)

## Guardrails

- Use docs as source of truth; do not infer missing facts.
- Prefer absolute file paths in responses.
- If canonical docs are missing, state that and fall back to `AGENTS.md` + `README.md` + `git status`.
- Keep kickoff concise; avoid long architecture retell unless user asks.

## References

- See `references/file-priority.md` for file precedence and fallback behavior.
