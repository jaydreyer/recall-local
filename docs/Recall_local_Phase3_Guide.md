# Recall.local - Phase 3 Guide

Purpose: define the post-Phase-2 execution plan to make Recall.local easier to operate daily, less curl-driven, and more interview-demonstrable.

## Phase 3 goal

Move from "demo-ready backend" to "operator-ready product surface" with:

1. UI-first usage paths (minimal manual curl).
2. Higher retrieval quality controls (hybrid/reranker/eval scoring track).
3. Operational reliability for repeatable demos and handoff.

Phase 3 is an extension phase. Phase 2 remains the hard gate for core scope completion.

## Phase 3 sub-phases

| Sub-phase | Scope | Exit criteria |
|---|---|---|
| `3A` Operator UX and UI paths | Replace repetitive curl operations with reusable UI/template flows in Open WebUI + n8n forms/webhooks; add one-click runbooks for ingestion/query/evals. | A user can ingest, run job-search query mode, run learning mode, and run scheduled eval from UI or single scripts without hand-editing JSON/curl. |
| `3B` Retrieval quality upgrades | Add optional hybrid retrieval (sparse + vector), optional reranker stage, and richer eval scoring (golden sets + optional RAGAS lane). | Quality track shows measurable improvement (or documented tradeoff) on held-out eval suites with reproducible before/after artifacts. |
| `3C` Operations + portfolio packaging | Harden restart/backup/recovery and produce polished demo evidence pack (artifacts, traces, architecture walk-through). | Cold-start-to-demo runbook passes on ai-lab; backup/restore smoke test passes; portfolio package is ready for interview walkthroughs. |

## 3A - Operator UX and UI paths

### Deliverables

1. Open WebUI templates for:
   - default RAG
   - `mode=job-search`
   - `mode=learning`
2. n8n webhook forms/templates for:
   - bookmarklet ingestion
   - meeting action extraction
3. Helper scripts for common operations (no payload editing):
   - `/Users/jaydreyer/projects/recall-local/scripts/rehearsal/run_phase2_demo_rehearsal.sh` (already present; keep current)
   - add small wrappers for "ingest manifest now", "run all evals now", "run one query mode now"
4. Docs refresh for operator flow:
   - where to click, where artifacts land, and fallback CLI commands.

### Acceptance checks

1. No direct curl required for standard daily loop:
   - ingest data
   - ask in job-search mode
   - ask in learning mode
   - run scheduled eval suite manually
2. New-handoff test:
   - a second user can complete the flow using docs only.

## 3B - Retrieval quality upgrades

### Deliverables

1. Golden eval expansion:
   - grow from small suites to stable, versioned golden sets per mode.
2. Optional hybrid retrieval lane:
   - sparse + dense fusion (for example BM25 + vector + fusion ranking).
3. Optional reranker lane:
   - rerank top-k before generation.
4. Scoring layer:
   - existing pass/fail checks remain primary gate;
   - optional semantic scoring lane (for example RAGAS) logged as secondary signal.

### Acceptance checks

1. Each quality change has:
   - baseline run artifact
   - candidate run artifact
   - explicit pass/fail or tradeoff note (quality vs latency/cost).
2. Default mode remains stable:
   - no regression to core/job-search/learning gates.

## 3C - Operations + portfolio packaging

### Deliverables

1. Reliability scripts:
   - service preflight
   - deterministic restart
   - backup/restore for SQLite + Qdrant payload snapshots
2. Observability alignment:
   - Langfuse lane documented as optional-but-supported if enabled.
3. Portfolio bundle:
   - one architecture diagram
   - one clean rehearsal log
   - one eval trend snapshot
   - one failure/recovery example

### Acceptance checks

1. Cold-start run:
   - services start cleanly
   - one ingest + one query + one eval pass executed end-to-end.
2. Recovery run:
   - restore from backup and re-run a core eval suite successfully.

## Recommended execution order

1. `3A` first (fastest operator productivity gain; directly removes curl friction).
2. `3B` second (quality improvements once operator path is stable).
3. `3C` third (hardening + portfolio packaging on top of stabilized flows).

## Constraints and non-goals

1. Keep Python scripts as system-of-record business logic; n8n remains orchestration.
2. Do not replace existing artifact-driven model with a custom dashboard rewrite.
3. Any retrieval-quality feature must ship behind an explicit mode/flag before becoming default.
4. Keep sync discipline:
   - local Mac edits must sync to ai-lab before runtime validation.

## Phase 3 completion gate

Phase 3 is complete when all are true:

1. UI-driven daily flow works without ad-hoc curl payload construction.
2. At least one retrieval-quality upgrade is shipped with documented eval evidence.
3. Backup/restore + cold-start walkthrough is documented and verified.
4. Portfolio demo package is complete and reproducible on ai-lab.
