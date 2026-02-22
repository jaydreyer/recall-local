# Context Kickoff Kit

This folder is a shareable starter kit for the `context-kickoff` skill pattern.

## Contents

- `context-kickoff/SKILL.md`
- `context-kickoff/agents/openai.yaml`
- `context-kickoff/references/file-priority.md`
- `context-kickoff/scripts/discover_context.sh`

## Install

```bash
mkdir -p ~/.codex/skills
cp -R ./context-kickoff ~/.codex/skills/context-kickoff
```

Then restart Codex.

## Validate (optional)

```bash
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/context-kickoff
```

## First Use

```text
Use $context-kickoff
```
