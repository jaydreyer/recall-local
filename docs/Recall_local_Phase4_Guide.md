# Recall.local - Phase 4 Guide

Purpose: move from "Phase 3 complete" to "repeatable release cadence" with reliability telemetry, CI checks, and operator-safe maintenance workflows.

## Phase 4 goal

Create a low-risk operating loop where changes can be validated, shipped, and verified with less manual intervention and clearer regression signals.

## Phase 4 sub-phases

| Sub-phase | Scope | Exit criteria |
|---|---|---|
| `4A` Reliability telemetry and soak lane | Add repeatable soak runs, pass-rate trend snapshots, and alert thresholds for core and job-search suites. | 7-day eval trend artifact exists with explicit pass/fail thresholds and no unknown red runs. |
| `4B` CI and release guardrails | Add CI checks for lint/test/smoke, plus release checklist + tag workflow. | Pull requests and release candidates have deterministic green/red quality gates. |
| `4C` Operator maintenance and hygiene | Standardize sync/restart/backup cadence, cleanup tasks, and rollback drills. | Operator runbook supports weekly maintenance and monthly restore drill with evidence logs. |

## 4A - Reliability telemetry and soak lane

### Deliverables

1. Soak runner wrapper (N iterations) for:
   - core eval suite
   - job-search eval suite
2. Trend artifact output:
   - pass-rate by run
   - latency trend by run
   - failure reason histogram (if any)
3. Alerting thresholds documented:
   - minimum pass-rate
   - max tolerated latency
   - escalation action when threshold fails

### Acceptance checks

1. At least 5 sequential runs captured for core + job-search with artifacted summary.
2. Any failing run includes machine-readable reason breakdown.

## 4B - CI and release guardrails

### Deliverables

1. CI workflow(s) on GitHub Actions:
   - Python syntax/static checks for `scripts/`
   - lightweight smoke checks for wrappers/help output
2. Release checklist doc:
   - pre-release validation commands
   - tag + push sequence
   - rollback steps
3. Tag convention enforcement:
   - `v0.x-*` semantic progression and changelog note template

### Acceptance checks

1. PR to `main` shows CI status checks with deterministic pass/fail behavior.
2. Release tag flow can be run from docs only by a second operator.

## 4C - Operator maintenance and hygiene

### Deliverables

1. Weekly maintenance script/runbook section:
   - sync status
   - preflight
   - stale artifact cleanup
2. Monthly recovery drill wrapper:
   - backup
   - restore to test path/collection
   - core eval verification
3. Workspace hygiene checks:
   - no unexpected `._*` metadata files
   - no stale stashes on ai-lab runtime repo

### Acceptance checks

1. Weekly maintenance execution log exists for two consecutive weeks.
2. Monthly recovery drill log exists and ends with eval pass evidence.

## Milestone 1 backlog (start here)

1. Add `scripts/phase4/run_eval_soak_now.sh` to execute repeated evals with summary JSON.
2. Add `scripts/phase4/summarize_eval_trend.py` to produce trend markdown + JSON.
3. Add `docs/Recall_local_Release_Checklist.md` with tag/rollback flow.
4. Add first CI workflow under `.github/workflows/` for syntax/smoke checks.
5. Add `scripts/phase4/run_repo_hygiene_check.sh` to flag `._*`, stale stashes, and dirty ai-lab repo.

## Constraints and non-goals

1. Keep Python scripts as source-of-truth logic; avoid moving logic into n8n nodes.
2. Do not broaden product feature scope in Phase 4; focus on operational repeatability.
3. Keep ai-lab sync discipline before runtime validation.

## Phase 4 completion gate

Phase 4 is complete when all are true:

1. Soak and trend telemetry exists and is used for go/no-go decisions.
2. CI and release checklist are required and reproducible.
3. Maintenance/recovery hygiene loop is documented and demonstrated with evidence.
