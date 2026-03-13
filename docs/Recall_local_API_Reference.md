# Recall.local API Reference

This document is the reviewer-facing entrypoint for the Recall.local FastAPI bridge.

The live API contract is generated from [../scripts/phase1/ingest_bridge_api.py](../scripts/phase1/ingest_bridge_api.py), which already exposes OpenAPI and interactive docs.

## Resource Model Overview

Recall.local uses a collection-first `v1` API with plural noun resources:

- `ingestions`: create document and file ingestion operations
- `rag-queries`: run cited retrieval-augmented queries
- `meeting-action-items`: extract structured notes and action items from transcripts
- `activities`: inspect recent ingestion activity
- `evaluations` and `evaluation-runs`: review and trigger evals
- `vault-files` and `vault-syncs`: inspect and sync an Obsidian vault
- `jobs`, `job-stats`, `job-gaps`, `job-deduplications`, `job-discovery-runs`, `job-evaluation-runs`: Phase 6 job-search operations
- `resumes`: ingest and inspect resume content used during fit evaluation
- `companies` and `company-profile-refresh-runs`: company intelligence and refresh workflows
- `llm-settings`: review and patch evaluation model settings
- `cover-letter-drafts`: generate cover-letter drafts from current job and resume context

## Interactive API Docs

When the bridge is running, open:

- Swagger UI: `http://localhost:8090/docs`
- ReDoc: `http://localhost:8090/redoc`
- OpenAPI JSON: `http://localhost:8090/openapi.json`

The OpenAPI app configuration also defines explicit server entries so FastAPI "Try it out" flows work cleanly for local and ai-lab environments.

## Endpoint Groups

The bridge currently organizes its endpoints into these tagged groups:

- `Health`: service liveness and readiness
- `Dashboard`: cache/readiness checks for the daily dashboard
- `Ingestions`: text and file ingestion operations
- `RAG Queries`: cited query execution over the vector store
- `Meeting Action Items`: structured meeting extraction
- `Auto Tag Rules`: shared configuration for clients
- `Vault`: Obsidian vault listing and syncs
- `Activities`: recent ingestion activity history
- `Evaluations`: eval history and eval run triggers
- `Jobs`: Phase 6 job listing, inspection, patching, and aggregate views
- `Resumes`: current resume ingestion and inspection
- `Companies`: company profile reads and refresh runs
- `LLM Settings`: evaluation model settings reads and partial updates
- `Cover Letter Drafts`: draft generation from job plus resume context

## Representative Endpoints

These are a few high-signal routes reviewers can inspect quickly:

- `GET /v1/healthz`: bridge health check
- `POST /v1/ingestions`: ingest structured text payloads
- `POST /v1/ingestions/files`: upload files for ingestion
- `POST /v1/rag-queries`: run cited RAG queries
- `GET /v1/activities`: review recent ingestion activity
- `GET /v1/evaluations`: inspect eval summaries
- `GET /v1/jobs`: list jobs with filtering and search
- `PATCH /v1/jobs/{jobId}`: update job metadata
- `POST /v1/job-evaluation-runs`: trigger job-fit evaluation runs
- `GET /v1/job-stats`: aggregate Phase 6 job metrics
- `GET /v1/job-gaps`: summarize recurring fit gaps
- `POST /v1/resumes`: ingest the active resume
- `GET /v1/companies`: list tracked companies
- `PATCH /v1/llm-settings`: update evaluation model settings
- `POST /v1/cover-letter-drafts`: generate a tailored draft

## Authentication And Request Conventions

- API key auth is optional and controlled by environment configuration.
- When enabled, callers send the key in the `X-API-Key` header.
- Responses include `X-Request-Id`, and error payloads include a matching `requestId` for tracing.
- The API is intentionally canonical on `/v1/*`; older compatibility aliases were removed during the canonical-only cutover.

## Why The API Looks This Way

The bridge is intentionally broad because it serves as the system contract shared by:

- the operator dashboard
- the daily dashboard
- n8n automation workflows
- local scripts and smoke checks

That consolidation is a design choice: it makes the system easier to demo, test, and reason about because every client uses the same noun-based contract instead of bespoke integration paths.

## Recommended Reviewer Path

If you want the fastest tour of the backend:

1. Open [../scripts/phase1/ingest_bridge_api.py](../scripts/phase1/ingest_bridge_api.py) and inspect `create_app()`.
2. Scan [../tests/test_bridge_api_contract.py](../tests/test_bridge_api_contract.py) to see how the API contract is regression-tested.
3. Read [Recall_local_Design_Decisions.md](Recall_local_Design_Decisions.md) for the architectural tradeoffs behind the surface area.
