# Context Kickoff Sharing Guide

Use this guide to share the `context-kickoff` pattern with other Codex users.

## What It Solves

Long chats accumulate stale assumptions. `context-kickoff` makes each new chat deterministic by loading canonical docs first and producing a concise startup snapshot.

## Pattern

1. Keep canonical docs in each repo:
- `docs/ENVIRONMENT_INVENTORY.md`
- `docs/IMPLEMENTATION_LOG.md`
- `docs/README.md`
2. Start each chat with:
- `Use $context-kickoff`
3. Continue tasking with explicit boundary:
- `Use $context-kickoff, then <task>. Update docs as you go.`

## Copy/Paste Prompts

### New Repo Bootstrap

```text
Use $context-kickoff.

Project bootstrap tasks:
1) Create/normalize canonical context docs:
   - docs/README.md
   - docs/ENVIRONMENT_INVENTORY.md
   - docs/IMPLEMENTATION_LOG.md
2) Populate them from current repo + runtime reality (services, hosts, ports, env/model/provider state, phase/status, blockers).
3) Add a strict documentation policy:
   - every meaningful infra/code/process change must update IMPLEMENTATION_LOG.md
   - any live-state change must update ENVIRONMENT_INVENTORY.md
   - doc updates happen in the same commit as the change
4) Run kickoff discovery and return:
   - Status (1 sentence)
   - Facts (3-6 bullets)
   - Risks (0-3 bullets)
   - Next (top 3 actions)
```

### Normal Daily Use

```text
Use $context-kickoff, then <task>. Update docs as you go.
```

## Before/After Example

### Before

- Assistant starts coding from stale chat context.
- Runtime assumptions are wrong.
- Status is scattered across messages.

### After

- Assistant runs kickoff discovery.
- Canonical docs are read first.
- Output begins with `Status/Facts/Risks/Next`.

## Troubleshooting

- If output says fallback was used, verify the skill script path exists.
- Literal `\n` in discovery output is formatting noise, not failure.
- Empty `phase/prd candidates` means no matching docs filenames were found.

## Share Package

A reusable package is provided at:

- `<repo-root>/docs/context-kickoff-kit/`

It includes a sanitized skill folder ready to copy into `~/.codex/skills/context-kickoff`.

## Redaction Guidance

Before sharing publicly, remove or generalize:

- private hostnames/IPs
- user home paths
- credentials/tokens
- internal project names
