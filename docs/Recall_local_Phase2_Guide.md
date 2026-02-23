# Recall.local - Phase 2 Guide

Purpose: execute Phase 2 as a demo-ready hardening pass after Phase 1 completion.

## Phase 2 goal

Deliver a reliable end-to-end demo flow that adds meeting action extraction, stronger ingestion coverage, observability, and polished artifact/audit visibility.

Source of truth: `/Users/jaydreyer/projects/recall-local/docs/Recall_local_PRD.md` (Phase 2 section).

## Phase 2 sub-phases

| Sub-phase | Scope | Exit criteria |
|---|---|---|
| `2A` Workflow 03 Core | Implement Meeting -> Action Items pipeline with strict structured validation and artifact output. | Transcript webhook returns validated structured output; Markdown artifact saved under `/data/artifacts/meetings/`; meeting summary indexed in `recall_docs`; run logged in SQLite. |
| `2B` Ingestion Expansion | Add Google Docs ingestion via n8n Google Docs node and ship browser bookmarklet ingestion path. | Google Doc URL/ID ingestion and browser bookmarklet ingestion both work end-to-end and are searchable in Qdrant; metadata includes source + channel; run/audit records present. |
| `2C` Observability + Artifact Polish | Integrate Langfuse tracing in `llm_client.py`; ensure artifact viewer presents ingestion, RAG, meetings, and eval outputs consistently. | Every `generate()` and `embed()` call visible in Langfuse with latency/tokens; artifacts browseable from a single index; audit fields visible on every response payload. |
| `2D` Demo Reliability Gate | Rehearse and harden the 10-minute demo script with failure handling and known-good fixtures. | Full script runs without failure; at least 3 channels ingest successfully in the same rehearsal; RAG and meeting outputs validated; eval run is green at end of rehearsal. |

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

3. **Observability layer (demo polish + debugging power):**
   - Self-hosted Langfuse deployment in Docker stack.
   - Instrument all LLM calls centrally in `scripts/llm_client.py`.
   - Trace retrieval -> prompt assembly -> generation -> validation for demos and debugging.

4. **Demo reliability and presentation:**
   - Single artifact-view path for evals, RAG responses, meeting outputs, ingest logs.
   - Rehearsed script with known-good inputs and fallback settings.
   - Explicit regression checks before each demo run.

## Suggested implementation order

1. Build `2A` first: meeting extraction workflow and output contract.
2. Add `2B` next: Google Docs and browser bookmarklet ingestion paths.
3. Add `2C`: Langfuse and artifact polish once new workflows are stable.
4. Finish with `2D`: scripted rehearsal and reliability gate.

## Risks and guardrails

- Keep n8n for orchestration only; heavy logic remains in Python scripts.
- Reuse existing validation and retry patterns from Workflow 02.
- Enforce strict non-goals: no dashboard rewrite, no intent-router complexity.
- Require a green eval run as part of phase closeout.

## Phase 2 completion gate

Phase 2 is complete only when all of the following are true:

1. Workflow 03 produces validated meeting action artifacts from transcript input.
2. Google Docs and browser bookmarklet ingestion both work and indexed content is queryable via Workflow 02.
3. Langfuse traces are live for all LLM calls.
4. Artifact browsing covers ingestion, RAG, meetings, and eval reports.
5. The full 10-minute demo script runs clean end-to-end.
