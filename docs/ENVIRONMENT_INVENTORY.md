# Recall.local Environment Inventory

Last updated: 2026-02-21

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
- Current status: placeholders still present (cloud fallback not yet validated).

## Skills Baseline (local Codex)

- Newly added in this setup pass:
  - `jupyter-notebook`
  - `transcribe`
  - `spreadsheet`
  - `security-ownership-map`

## Update Rule

Whenever services, ports, paths, provider config, or deployment topology changes, update this file in the same commit.

