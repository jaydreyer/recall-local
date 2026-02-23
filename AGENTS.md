# Agent Instructions

## Mandatory Sync Rule (Mac -> ai-lab)

Whenever code is created or updated locally on `/Users/jaydreyer/projects/recall-local`, sync those changes to `ai-lab` (`/home/jaydreyer/recall-local`) before any ai-lab restart, curl verification, or n8n validation.

Do not assume ai-lab has current code until sync is complete and spot-checked.

## Verification After Sync

After syncing, run at least one quick file-content check on `ai-lab` (for example with `rg` on newly added route/function names) before troubleshooting runtime errors.
