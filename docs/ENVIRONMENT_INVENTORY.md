# Recall.local Environment Inventory

Last updated: 2026-02-22

## Decision Snapshot

- Delivery mode: **Approach B** from Phase 0 guide.
- Rationale: preserve currently running production-use services and add only missing Recall.local components.

## GitHub

- Repository: [https://github.com/jaydreyer/recall-local](https://github.com/jaydreyer/recall-local)
- Visibility: `PRIVATE`
- Default branch: `main`

## Runtime Host (`ai-lab`)

- SSH user: `jaydreyer`
- Tailscale address: `100.116.103.78`
- Repo path: `/home/jaydreyer/recall-local`

## Active Services (current known baseline)

- `ollama` container: `0.0.0.0:11434->11434`
- `qdrant` container: `0.0.0.0:6333-6334->6333-6334`
- `n8n` container: `0.0.0.0:5678->5678`
- `recall-ingest-bridge` container: `0.0.0.0:8090->8090`
- `open-webui` container: `0.0.0.0:3000->8080`
- `caddy` container: `0.0.0.0:80,443`
- `portainer` container: `0.0.0.0:9000`
- `recall-mkdocs` container: `0.0.0.0:8100->8000`

## Data and Storage

- Incoming documents: `/home/jaydreyer/recall-local/data/incoming`
- Processed documents: `/home/jaydreyer/recall-local/data/processed`
- Artifacts: `/home/jaydreyer/recall-local/data/artifacts`
- SQLite DB: `/home/jaydreyer/recall-local/data/recall.db`

## Qdrant

- Health endpoint: `http://localhost:6333/healthz`
- Primary Recall collection: `recall_docs`
- Vector size: `768`
- Distance metric: cosine

## LLM Runtime

- Local endpoint: `http://localhost:11434`
- Installed models observed:
  - `nomic-embed-text:latest`
  - `phi3:mini`
  - `mistral:7b`
  - `llama3.2:3b`
- `.env.example` default model: `llama3.2:3b`

## Cloud Providers

- Config keys expected in `docker/.env`:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `GEMINI_API_KEY`
- Validation status on `ai-lab`:
  - Anthropic: pass
  - OpenAI: pass
  - Gemini: pass after model update to `gemini-2.5-flash`
- `.env.example` default Gemini model: `gemini-2.5-flash`

## n8n Ingestion Webhook

- Unified webhook endpoint (local on server): `http://localhost:5678/webhook/recall-ingest`
- Validation status: `HTTP 200` for test payload (verified 2026-02-22)
- Backing workflow:
  - Active: `qKMhxYULZoPwXnDI` (`Recall Ingest Webhook v2`)
  - Inactive legacy: `aOyMgFwit2mS82pP` (`Recall Ingest Webhook`)

## n8n Query Webhook (Workflow 02)

- Query webhook endpoint (local on server): `http://localhost:5678/webhook/recall-query`
- Backing bridge endpoint (server): `http://localhost:8090/query/rag`
- Validation status:
  - Bridge route: `HTTP 200` for dry-run query payload (verified 2026-02-22)
  - n8n production webhook: `HTTP 200` with cited RAG JSON payload (verified 2026-02-22)
- Deployment mode note:
  - n8n container does not include `python3`; `Execute Command`-based Workflow 02 fails with `/bin/sh: python3: not found`.
  - Use HTTP bridge workflow for Workflow 02 in this environment.

## Execution Debug Rule (n8n)

- For webhook failures, inspect n8n `Executions` first and use failed node + error details as source of truth before changing workflow wiring.

## Hostname/Port Scope Rule

- `localhost` always means the current machine/container.
- From MacBook, use `http://100.116.103.78:<port>` for ai-lab services.
- From ai-lab shell, use `http://localhost:<port>` for host-published services.

## Phase Status

- Phase 0: complete (all baseline checks and ingestion webhook validation done)
- Phase 1: complete (`1A`-`1D` done; Workflow 02 webhook live and eval suite passing)

## Skills Baseline (local Codex)

- Newly added in this setup pass:
  - `jupyter-notebook`
  - `transcribe`
  - `spreadsheet`
  - `security-ownership-map`

## Update Rule

Whenever services, ports, paths, provider config, or deployment topology changes, update this file in the same commit.
