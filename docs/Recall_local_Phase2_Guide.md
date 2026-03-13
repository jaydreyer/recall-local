# Recall.local - Phase 2 Guide

Purpose: execute Phase 2 as a demo-ready hardening pass after Phase 1 completion.

## Phase 2 goal

Deliver a reliable end-to-end demo flow that adds meeting action extraction, stronger ingestion coverage, domain-scoped RAG personas, observability, and polished artifact/audit visibility.

Source of truth: `<repo-root>/docs/Recall_local_PRD.md` (Phase 2 section).
Execution checklist: `<repo-root>/docs/Recall_local_Phase2_Checklists.md`.

## Phase 2 sub-phases

| Sub-phase | Scope | Exit criteria |
|---|---|---|
| `2A` Workflow 03 Core | Implement Meeting -> Action Items pipeline with strict structured validation and artifact output. | Transcript webhook returns validated structured output; Markdown artifact saved under `/data/artifacts/meetings/`; meeting summary indexed in `recall_docs`; run logged in SQLite. |
| `2B` Ingestion Expansion + Corpus Hygiene | Add Google Docs ingestion via n8n Google Docs node and ship browser bookmarklet ingestion path; standardize tagging and re-ingestion rules for high-churn job-search sources. | Google Doc URL/ID ingestion and browser bookmarklet ingestion both work end-to-end and are searchable in Qdrant; metadata includes source + channel + tags; source-based replacement policy is defined and tested for mutable sources (for example job descriptions). |
| `2C` Domain-Scoped RAG + Observability | Add Workflow 02 optional tag-scoped retrieval (`filter_tags`), ship job-search prompt profile, integrate Langfuse tracing in `llm_client.py`, and keep artifact viewer output consistent. | `filter_tags` works end-to-end via Workflow 02 payload and Open WebUI template; job-search prompt returns valid Workflow 02 JSON with citation pairs; every `generate()` and `embed()` call visible in Langfuse with latency/tokens; artifacts browseable from a single index. |
| `2D` Demo Reliability Gate | Rehearse and harden the 10-minute demo script with failure handling, known-good fixtures, and domain eval gates. | Full script runs without failure; at least 3 channels ingest successfully in the same rehearsal; general RAG + meeting outputs validated; both core eval and job-search eval suites are green at end of rehearsal. |

## What we are going to build

1. **Meeting workflow (new core capability):**
   - New webhook + runner for transcript ingestion and action extraction.
   - Prompt + schema for decisions, action items (owner, due date, description), risks, follow-ups.
   - Validation/retry behavior matching Workflow 02 quality standards.
   - Markdown artifact generator + optional summary indexing.

2. **Google Docs + browser bookmarklet channels (mandatory in Phase 2):**
   - n8n flow to fetch Google Doc content by URL/ID.
   - Browser bookmarklet posts page URL/content into unified webhook ingestion path.
   - Normalize into existing ingestion payload model and reuse Workflow 01 internals.
   - Preserve provenance metadata for citations/auditability.
   - Define and enforce source-based replacement for mutable job-search corpus inputs (JDs, prep notes) so stale versions do not accumulate.

3. **Domain-scoped RAG persona layer (job search use case on shared stack):**
   - Add optional Workflow 02 `filter_tags` parameter and retrieval filter behavior.
   - Add an Open WebUI Job Search template that sets `filter_tags: ["job-search"]`.
   - Add `/prompts/job_search_coach.md` while preserving strict Workflow 02 JSON output contract (`answer`, `citations[]`, `confidence_level`, `assumptions`).
   - Add job-search eval cases as a separate case file executed by the same eval harness.

4. **Observability layer (demo polish + debugging power):**
   - Self-hosted Langfuse deployment in Docker stack.
   - Instrument all LLM calls centrally in `scripts/llm_client.py`.
   - Trace retrieval -> prompt assembly -> generation -> validation for demos and debugging.

5. **Demo reliability and presentation:**
   - Single artifact-view path for evals, RAG responses, meeting outputs, ingest logs.
   - Rehearsed script with known-good inputs and fallback settings.
   - Explicit regression checks before each demo run, including job-search suite.

## Suggested implementation order

1. Build `2A` first: meeting extraction workflow and output contract.
2. Add `2B` next: Google Docs and browser bookmarklet ingestion paths plus source-based replacement policy for mutable sources.
3. Add `2C`: tag-scoped retrieval, job-search prompt profile, and job-search eval cases.
4. Continue `2C` with observability tasks: Langfuse and artifact polish once domain-scoped RAG is stable.
5. Finish with `2D`: scripted rehearsal and reliability gate.

## 2A Core Interfaces (implemented)

- Runner script:
  - `<repo-root>/scripts/phase2/meeting_action_items.py`
- Payload runner:
  - `<repo-root>/scripts/phase2/meeting_from_payload.py`
- HTTP bridge endpoints:
  - `/v1/meeting-action-items` (canonical)
  - `/meeting/action-items` (alias)
  - `/meeting/actions` (alias)
  - `/query/meeting` (alias)
- Prompt templates:
  - `<repo-root>/prompts/workflow_03_meeting_extract.md`
  - `<repo-root>/prompts/workflow_03_meeting_extract_retry.md`
- Payload example:
  - `<repo-root>/n8n/workflows/payload_examples/meeting_action_items_payload_example.json`
- n8n wiring runbook:
  - `<repo-root>/n8n/workflows/PHASE2A_WORKFLOW03_WIRING.md`
- bridge verification helper:
  - `<repo-root>/scripts/phase2/verify_workflow03_bridge.py`

Initial contract behavior:
- returns validated structured JSON
- writes meeting artifact Markdown under `/data/artifacts/meetings/`
- indexes meeting summary into `recall_docs`
- logs run metadata in SQLite `runs`

## 2B Ingestion controls (implemented)

- Unified webhook normalization now supports bookmarklet + gdoc-friendly payloads and preserves tags:
  - `<repo-root>/scripts/phase1/channel_adapters.py`
  - `<repo-root>/scripts/phase1/ingest_from_payload.py`
- Source-based replacement controls for mutable sources:
  - request fields: `replace_existing` (boolean), `source_key` (stable key)
  - canonical source identity persisted to Qdrant payload field `source_identity`
  - replacement activity exposed in ingestion result fields (`replace_existing`, `replaced_points`, `replacement_status`)
  - implementation: `<repo-root>/scripts/phase1/ingestion_pipeline.py`
- Bridge route supports bookmarklet path directly:
  - `/v1/ingestions` (canonical, with `channel=bookmarklet`)
  - `/ingest/bookmarklet` (alias)
  - implementation: `<repo-root>/scripts/phase1/ingest_bridge_api.py`
- Phase 2B payload/runbook assets:
  - `<repo-root>/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json`
  - `<repo-root>/n8n/workflows/payload_examples/gdoc_ingest_payload_example.json`
  - `<repo-root>/n8n/workflows/PHASE1B_CHANNEL_WIRING.md`

Operational rule for job-search corpus:
- `job-search` tag is mandatory at ingestion time.
- Mutable job-search sources (JDs/prep docs) should ingest with `replace_existing=true` and stable `source_key`.

## 2C Domain-scoped RAG controls (implemented)

- Workflow 02 retrieval now supports optional tag filtering:
  - payload field: `filter_tags` (array or comma-separated string)
  - retrieval filter behavior: when present, Qdrant query restricts results to matching tags
  - implementation:
    - `<repo-root>/scripts/phase1/retrieval.py`
    - `<repo-root>/scripts/phase1/rag_query.py`
    - `<repo-root>/scripts/phase1/rag_from_payload.py`
    - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
- Workflow 02 prompt mode now supports:
  - `mode=default` -> `<repo-root>/prompts/workflow_02_rag_answer.md`
  - `mode=job-search` -> `<repo-root>/prompts/job_search_coach.md`
  - `mode=learning` -> `<repo-root>/prompts/learning_coach.md`
- Workflow 02 response/audit now includes:
  - `sources[].tags`
  - `audit.mode`
  - `audit.filter_tags`
  - `audit.prompt_profile`
- Job-search eval suite added to shared harness:
  - `<repo-root>/scripts/eval/job_search_eval_cases.json`
  - `<repo-root>/scripts/eval/run_eval.py`
  - includes checks for required source tags and required grounding terms
- Scheduled eval runner now executes both suites:
  - core: `<repo-root>/scripts/eval/eval_cases.json`
  - job-search: `<repo-root>/scripts/eval/job_search_eval_cases.json`
  - script: `<repo-root>/scripts/eval/scheduled_eval.sh`
- Optional Langfuse instrumentation hooks added in LLM client:
  - `<repo-root>/scripts/llm_client.py`
  - enabled with `RECALL_LANGFUSE_ENABLED=true` and Langfuse keys
  - trace metadata includes workflow/mode context when passed by callers (for example Workflow 02)
- Batch ingest helper for job-search corpus (reduces repeated curl usage):
  - `<repo-root>/scripts/phase2/ingest_job_search_manifest.py`
  - manifest template: `<repo-root>/scripts/phase2/job_search_manifest.example.json`
  - optional CLI flag `--ensure-tag` for explicit tag enforcement when desired

## Risks and guardrails

- Keep n8n for orchestration only; heavy logic remains in Python scripts.
- Reuse existing validation and retry patterns from Workflow 02.
- Keep a single `recall_docs` collection; use optional tag filtering instead of collection sprawl.
- Keep one eval harness implementation; add domain suites as additional case files rather than forked evaluators.
- Enforce strict JSON output contract for all prompt profiles, including job-search mode.
- Enforce strict non-goals: no dashboard rewrite, no intent-router complexity.
- Require a green eval run as part of phase closeout.

## Phase 2 completion gate

Phase 2 is complete only when all of the following are true:

1. Workflow 03 produces validated meeting action artifacts from transcript input.
2. Google Docs and browser bookmarklet ingestion both work and indexed content is queryable via Workflow 02.
3. Workflow 02 supports optional `filter_tags` and Open WebUI Job Search mode routes requests with `filter_tags=["job-search"]`.
4. Source-based replacement policy is implemented for mutable corpus items (for example job descriptions), preventing stale duplicates from polluting retrieval.
5. Job-search prompt profile is live and passes strict JSON + citation validation contract.
6. Core eval suite and job-search eval suite both run green using the shared eval harness.
7. Langfuse traces are live for all LLM calls.
8. Artifact browsing covers ingestion, RAG, meetings, and eval reports.
9. The full 10-minute demo script runs clean end-to-end.
