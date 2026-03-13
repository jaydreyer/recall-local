# Recall.local - Phase 3A Operator Runbook

Purpose: provide no-curl operator paths for daily ingestion, query, and eval loops while Phase 3A is in progress.

## Scope in this first Phase 3A slice

This runbook covers:

1. one-command operator wrappers in `<repo-root>/scripts/phase3/`
2. Open WebUI template payloads for Workflow 02 mode routing
3. n8n form/webhook payload templates for bookmarklet ingestion and meeting extraction

## Operator wrappers (no payload editing)

### 1) Ingest manifest now

```bash
<repo-root>/scripts/phase3/run_ingest_manifest_now.sh
```

Common options:

- `--profile job-search|learning`
- `--manifest-file /absolute/path/to/manifest.json`
- `--ensure-tag job-search`
- `--dry-run`

Examples:

```bash
<repo-root>/scripts/phase3/run_ingest_manifest_now.sh --profile job-search
<repo-root>/scripts/phase3/run_ingest_manifest_now.sh --profile learning --dry-run
```

### 2) Run one query mode now

```bash
<repo-root>/scripts/phase3/run_query_mode_now.sh --mode default
```

Common options:

- `--mode default|job-search|learning`
- `--query "your question"`
- `--top-k 5`
- `--min-score 0.2`
- `--max-retries 1`
- `--dry-run`

Examples:

```bash
<repo-root>/scripts/phase3/run_query_mode_now.sh --mode job-search --query "What should I emphasize for an OpenAI SE interview?"
<repo-root>/scripts/phase3/run_query_mode_now.sh --mode learning --dry-run
```

### 3) Run all eval suites now

```bash
<repo-root>/scripts/phase3/run_all_evals_now.sh
```

Common options:

- `--n8n-host http://localhost:5678`
- `--webhook-url http://localhost:5678/webhook/recall-query`
- `--alert-webhook-url https://...`

## Open WebUI template payloads

Use these as request bodies when wiring Open WebUI tools/actions to Workflow 02 webhook (`/webhook/recall-query`).

### Default mode

```json
{
  "query": "{{prompt}}",
  "mode": "default",
  "top_k": 5,
  "min_score": 0.2,
  "max_retries": 1
}
```

### Job-search mode

```json
{
  "query": "{{prompt}}",
  "mode": "job-search",
  "filter_tags": ["job-search"],
  "top_k": 5,
  "min_score": 0.2,
  "max_retries": 1
}
```

### Learning mode

```json
{
  "query": "{{prompt}}",
  "mode": "learning",
  "filter_tags": ["learning", "genai-docs"],
  "top_k": 5,
  "min_score": 0.2,
  "max_retries": 0
}
```

## n8n form/webhook templates

Use existing payload examples as canonical templates:

- bookmarklet ingest: `<repo-root>/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json`
- meeting action extraction: `<repo-root>/n8n/workflows/payload_examples/meeting_action_items_payload_example.json`
- import-ready Phase 3A form workflows:
  - `<repo-root>/n8n/workflows/phase3a_bookmarklet_form_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase3a_meeting_action_form_http.workflow.json`
- wiring runbook:
  - `<repo-root>/n8n/workflows/PHASE3A_OPERATOR_FORMS_WIRING.md`

Recommended form mappings:

1. Bookmarklet form -> HTTP POST `http://localhost:8090/v1/ingestions` with fields `channel=bookmarklet`, `url`, `title`, `text`, `tags`, `replace_existing`, `source_key`, `source`.
2. Meeting form -> HTTP POST `http://localhost:8090/v1/meeting-action-items` with fields `meeting_title`, `transcript`, `source`, `source_ref`, `tags`.

## Validation checklist for this slice

1. Run one wrapper from each category (`ingest`, `query`, `eval`) without modifying JSON files.
2. Confirm query wrapper returns Workflow 02 JSON with `audit.mode`.
3. Confirm eval wrapper writes scheduled logs under `<repo-root>/data/artifacts/evals/scheduled/`.
