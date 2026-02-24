# Agent Instructions

## Mandatory Sync Rule (Mac -> ai-lab)

Whenever code is created or updated locally on `/Users/jaydreyer/projects/recall-local`, sync those changes to `ai-lab` (`/home/jaydreyer/recall-local`) before any ai-lab restart, curl verification, or n8n validation.

Do not assume ai-lab has current code until sync is complete and spot-checked.

## Verification After Sync

After syncing, run at least one quick file-content check on `ai-lab` (for example with `rg` on newly added route/function names) before troubleshooting runtime errors.

## API Skill Routing

For any task involving APIs (design, review, OpenAPI/Swagger specs, endpoint naming, request/response schemas, status codes, or API documentation), always use [$rest-api-design](/Users/jaydreyer/.codex/skills/rest-api-design/SKILL.md) and follow its workflow, non-negotiables, and output templates.

Only skip this skill if the Only skip this skill if the user explicitly requests a different approach, or it is impossible to implement due to extenuating circumstances. If the latter is the case, work with me on a solution.
