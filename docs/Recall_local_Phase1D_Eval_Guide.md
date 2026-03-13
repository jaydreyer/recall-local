# Recall.local - Phase 1D Eval Guide

Purpose: run citation/latency regression checks for Workflow 02 and persist results to SQLite + Markdown artifacts.

## Deliverables

- Eval runner:
  - `<repo-root>/scripts/eval/run_eval.py`
- Default eval cases (10 checks):
  - `<repo-root>/scripts/eval/eval_cases.json`
- Eval report artifacts:
  - `<repo-root>/data/artifacts/evals/`
- SQLite table:
  - `eval_results`

## Run Commands

From ai-lab host (recommended):

```bash
python3 <server-repo-root>/scripts/eval/run_eval.py \
  --backend webhook \
  --webhook-url http://localhost:5678/webhook/recall-query \
  --top-k 5 \
  --min-score 0.15 \
  --max-retries 1
```

From MacBook against ai-lab:

```bash
python3 <repo-root>/scripts/eval/run_eval.py \
  --backend webhook \
  --webhook-url http://<ai-lab-tailnet-ip>:5678/webhook/recall-query \
  --top-k 5 \
  --min-score 0.15 \
  --max-retries 1
```

Quick smoke (first 2 cases, no writes):

```bash
python3 <repo-root>/scripts/eval/run_eval.py \
  --backend webhook \
  --webhook-url http://<ai-lab-tailnet-ip>:5678/webhook/recall-query \
  --max-cases 2 \
  --dry-run
```

## Pass Criteria

For each case:

- Response has non-empty `citations[]`
- Every citation `doc_id` + `chunk_id` exists in response `sources[]`
- Latency is below threshold (`RECALL_EVAL_MAX_LATENCY_MS` or case override)
- If `expected_doc_id` is set in case file, first citation matches it

Overall run exits non-zero if any case fails.

## Eval Case Schema

`scripts/eval/eval_cases.json` supports:

- `question` (required)
- `expected_doc_id` (optional)
- `max_latency_ms` (optional)
- `expect_unanswerable` (optional, default `false`)

When `expect_unanswerable=true`, case passes only if:

- citations are valid if present (empty citation arrays are tolerated for abstentions)
- `confidence_level` is `low`
- answer includes explicit uncertainty/refusal language (for example, \"I don't have enough information...\")

## Debug Protocol (Mandatory)

When eval checks fail in webhook mode, follow this order:

1. Inspect n8n `Executions` first and identify failed node + error details.
2. If failed node is `Execute Command` and error contains `python3: not found`, switch Workflow 02 to HTTP bridge path.
3. Validate bridge route directly before retesting webhook:

```bash
curl -sS -X POST 'http://localhost:8090/query/rag?dry_run=true' \
  -H 'content-type: application/json' \
  -d '{"query":"smoke test","top_k":5,"min_score":0.15}'
```

4. Only after bridge is healthy, retest:

```bash
curl -sS -X POST http://localhost:5678/webhook/recall-query \
  -H 'content-type: application/json' \
  -d '{"query":"smoke test","top_k":5,"min_score":0.15}'
```

## Host Scope Reminder

- On ai-lab shell, `localhost` means ai-lab.
- On MacBook shell, `localhost` means MacBook. Use `http://<ai-lab-tailnet-ip>:<port>` for ai-lab services.

## Current Hardening Signal

As of 2026-02-22, answerable checks are green while the new unanswerable checks are red. This is expected for the first IDK gate rollout and should be treated as the next prompt/validation hardening target.
