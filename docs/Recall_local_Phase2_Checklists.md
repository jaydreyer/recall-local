# Recall.local - Phase 2 Implementation Checklists

Purpose: provide execution checklists for Phase 2 updates that incorporate job-search domain mode without adding new infrastructure.

Source plan: `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Guide.md`.

## Checklist `2B` - Ingestion Expansion + Corpus Hygiene

### 2B.1 Google Docs + browser bookmarklet ingestion

- [ ] Verify Google Docs ingestion path is wired and payload-normalized.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_from_payload.py`, `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py`
- [ ] Verify browser bookmarklet payload path reaches unified webhook and maps to standard ingestion request fields.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_from_payload.py`, `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_bridge_api.py`, `/Users/jaydreyer/projects/recall-local/n8n/workflows/`
- [ ] Confirm `metadata.tags` from webhook payload is preserved into Qdrant payload `tags`.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_from_payload.py`, `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py`

### 2B.2 Tagging rules for job-search corpus

- [ ] Define required tags for job-search corpus inputs in documentation/runbook (`job-search` mandatory).
  - files: `/Users/jaydreyer/projects/recall-local/docs/Recall_local_PRD_Addendum_JobSearch.md`, `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Guide.md`
- [ ] Add operational guidance for non-webhook ingestion (folder drop) so job-search files are tagged correctly before retrieval filtering is used.
  - files: `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Guide.md`, `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase1_Guide.md`

### 2B.3 Source-based replacement policy for mutable sources

- [ ] Implement deletion/replacement logic keyed by stable source identity (for example canonical URL/path) rather than `doc_id`.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py`
- [ ] Add payload-level controls for replacement behavior (for example `replace_existing=true` and canonical source key handling).
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_from_payload.py`, `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py`
- [ ] Record replacement activity in run/audit metadata so stale-source cleanup is inspectable.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py`

### 2B.4 Verification checklist

- [ ] Ingest one Google Doc and one bookmarklet URL with `tags=["job-search","anthropic"]`; verify both appear in Qdrant payload with those tags.
- [ ] Re-ingest an updated JD source with replacement enabled; verify prior chunks for same source are removed and only latest version is retrievable.
- [ ] Confirm ingestion logs/run artifacts capture source, channel, tag set, and replacement action metadata.

## Checklist `2C` - Domain-Scoped RAG + Observability

### 2C.1 Workflow 02 `filter_tags` support

- [ ] Add optional `filter_tags` handling to Workflow 02 request path.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_from_payload.py`, `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`
- [ ] Add Qdrant payload filter wiring in retrieval layer.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/retrieval.py`
- [ ] Keep backward compatibility: when `filter_tags` is absent or empty, retrieval behavior remains unchanged.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/retrieval.py`

### 2C.2 Job-search prompt profile

- [ ] Add job-search prompt template file that keeps Workflow 02 JSON response contract.
  - files: `/Users/jaydreyer/projects/recall-local/prompts/job_search_coach.md`
- [ ] Wire mode selection so job-search mode uses job-search prompt while preserving existing validator requirements (`doc_id` + `chunk_id` citations).
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`, `/Users/jaydreyer/projects/recall-local/scripts/validate_output.py`
- [ ] Add Open WebUI template payload configuration for job-search mode (`filter_tags=["job-search"]`).
  - files: `/Users/jaydreyer/projects/recall-local/n8n/workflows/`, Open WebUI prompt templates (runtime configuration)

### 2C.3 Job-search eval suite (shared harness)

- [ ] Create separate job-search eval cases file run by existing harness (do not fork eval code).
  - files: `/Users/jaydreyer/projects/recall-local/scripts/eval/job_search_eval_cases.json`, `/Users/jaydreyer/projects/recall-local/scripts/eval/run_eval.py`
- [ ] Add script/runbook entries for running both core and job-search suites.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/eval/scheduled_eval.sh`, `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Eval_Scheduling.md`
- [ ] Ensure job-search cases check for non-generic, user-context-grounded output in addition to citation/latency constraints.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/eval/run_eval.py`, `/Users/jaydreyer/projects/recall-local/scripts/eval/job_search_eval_cases.json`

### 2C.4 Langfuse + artifact polish

- [ ] Confirm tracing covers job-search mode and general mode with clear metadata segmentation.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/llm_client.py`
- [ ] Confirm artifact outputs make mode/filter context visible for post-run debugging.
  - files: `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`

### 2C.5 Verification checklist

- [ ] Run Workflow 02 query with `filter_tags=["job-search"]`; verify returned `sources[]` are all tagged `job-search`.
- [ ] Run same query without `filter_tags`; verify normal cross-domain retrieval behavior still works.
- [ ] Run job-search prompt mode and verify JSON schema + citation validation passes without fallback.
- [ ] Run both eval suites and confirm green status with separate artifacts:
  - core suite: `/Users/jaydreyer/projects/recall-local/scripts/eval/eval_cases.json`
  - job-search suite: `/Users/jaydreyer/projects/recall-local/scripts/eval/job_search_eval_cases.json`

## Suggested execution order

1. Complete `2B.1` and `2B.2` first so tag-aware corpus ingestion is reliable.
2. Implement `2B.3` replacement policy before adding heavy job-search corpus updates.
3. Implement `2C.1` retrieval filtering and prove backward compatibility.
4. Add `2C.2` prompt profile and keep schema compliance strict.
5. Add `2C.3` eval suite and wire scheduled execution.
6. Finish with `2C.4` observability polish and run full verification.

## Phase 2 gate tie-in

- `2B` checklist maps to Phase 2 gate items for ingestion + corpus hygiene.
- `2C` checklist maps to Phase 2 gate items for tag-scoped retrieval, job-search mode, eval coverage, and observability.
