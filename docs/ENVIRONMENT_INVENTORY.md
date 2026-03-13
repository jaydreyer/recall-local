# Recall.local Environment Inventory

Last updated: 2026-03-12

Public-repo note: host-specific paths, IPs, and hostnames are intentionally generalized with placeholders so the document stays shareable without losing operational meaning.

## Decision Snapshot

- Delivery mode: **Approach B** from Phase 0 guide.
- Rationale: preserve currently running production-use services and add only missing Recall.local components.

## GitHub

- Repository: [https://github.com/jaydreyer/recall-local](https://github.com/jaydreyer/recall-local)
- Visibility goal: public reviewer-facing repository
- Default branch: `main`

## Runtime Host (`ai-lab`)

- SSH user: `jaydreyer`
- Tailscale address: `<ai-lab-tailnet-ip>`
- Repo path: `<server-repo-root>`

## Active Services (current known baseline)

- `ollama` container: `0.0.0.0:11434->11434`
- `qdrant` container: `0.0.0.0:6333-6334->6333-6334`
- `n8n` container: `0.0.0.0:5678->5678`
- `recall-ingest-bridge` container: `0.0.0.0:8090->8090`
- `open-webui` container: `0.0.0.0:3000->8080`
- `caddy` container: `0.0.0.0:80,443`
- `portainer` container: `0.0.0.0:9000`
- `recall-mkdocs` container: `0.0.0.0:8100->8000`
- `recall-ui` container: `0.0.0.0:8170->80` (verified running on ai-lab via `scripts/phase5/run_operator_stack_now.sh up` on 2026-02-26)
- `recall-daily-dashboard` container: `0.0.0.0:3001->80` (verified running on ai-lab via `docker compose -f docker/docker-compose.yml up -d --build daily-dashboard` on 2026-03-04)
- `recall-daily-dashboard` HTTP check: `GET/HEAD http://<ai-lab-tailnet-ip>:3001` -> `200` after Phase 6D deploy validation on 2026-03-06
- dashboard smoke endpoint:
  - `GET http://localhost:8090/v1/dashboard-checks`
- dashboard smoke wrapper:
  - `<server-repo-root>/scripts/phase6/run_dashboard_smoke.sh`

## Data and Storage

- Incoming documents: `<server-repo-root>/data/incoming`
- Processed documents: `<server-repo-root>/data/processed`
- Artifacts: `<server-repo-root>/data/artifacts`
- SQLite DB: `<server-repo-root>/data/recall.db`
- Vault sync state DB (Phase 5C): `<server-repo-root>/data/vault_sync_state.db`
- Daily full-backup root: `<server-repo-root>/data/artifacts/backups/daily_full`
- Daily backup schedule on `ai-lab`: `2:15 AM` America/Chicago via cron
- Daily backup retention: `14` days
- Daily backup manual verification snapshot: `<server-repo-root>/data/artifacts/backups/daily_full/manual_verify_20260306T2006Z`
- Daily backup coverage:
  - logical SQLite + all Qdrant collections export
  - raw Qdrant Docker volume snapshot
  - `n8n` SQLite snapshot + archived `n8n/` runtime directory
  - archived `data/` tree excluding nested backup folders
  - `docker/.env`, `docker/.env.example`, `docker/docker-compose.yml`, and git revision snapshot

## Qdrant

- Health endpoint: `http://localhost:6333/healthz`
- Primary Recall collection: `recall_docs`
- Phase 6 collections: `recall_jobs`, `recall_resume`
- Vector size: `768`
- Distance metric: cosine
- Live state (ai-lab, 2026-03-06 after Phase 6D restore):
  - Phase 6 collections were recreated with `python3 scripts/phase6/setup_collections.py`.
  - `recall_resume` was reseeded from `<vault-root>/career/Jay-Dreyer-Resume.md`.
  - `recall_jobs` was repopulated from career-page discovery and later expanded with additional live discovery passes.
  - Current live bridge stats on 2026-03-07:
    - `total_jobs=984`
    - `career_page=881`
    - `jobspy=100`
    - `serpapi=2`
    - `chrome_extension=1`
  - Production bridge stats returned `high_fit_count=16` after a local evaluation pass with `llama3.2:3b`.

## OpenAI Career Source

- OpenAI tracking now uses:
  - ATS: `ashby`
  - Company board id: `openai`
  - Human-facing careers URL: `https://openai.com/careers/search/`
  - Data source URL: `https://api.ashbyhq.com/posting-api/job-board/openai`
- Live automation alignment on `ai-lab`:
  - bridge discovery runner supports `ashby`
  - bridge default `career_page` source limit is `25`
  - active n8n workflow `Recall Phase6B - Career Page Monitor (Traditional Import)` (`eE5wQFqV9oiSHKaL`) is published with the same OpenAI Ashby logic
- Current live OpenAI state on 2026-03-07:
  - `job_count=97`
  - source mix: `jobs.ashbyhq.com/openai/...` plus one preserved LinkedIn posting
  - operator backup of the pre-reseed OpenAI slice:
    - `<server-repo-root>/backups/20260307T-openai-reseed/openai_jobs.pre-reseed.json`

## LLM Runtime

- Local endpoint: `http://localhost:11434`
- Live ai-lab `.env` model invariant:
  - `RECALL_LLM_PROVIDER=ollama`
  - `OLLAMA_MODEL=qwen2.5:7b-instruct`
  - `OLLAMA_EMBED_MODEL=nomic-embed-text`
- Required live-model verification:
  - `docker exec -i ollama ollama list`
- `.env.example` default model: `qwen2.5:7b-instruct`

## Observability and Operator Checks

- Bridge request IDs:
  - bridge responses include `X-Request-Id`
  - error envelopes include `requestId`
- Langfuse:
  - optional tracing is wired in `scripts/llm_client.py`
  - enabled only when Langfuse env vars are present
- Canonical operator checks:
  - dashboard data readiness:
    - `<server-repo-root>/scripts/phase6/run_dashboard_smoke.sh`
  - consolidated operator observability:
    - `<server-repo-root>/scripts/phase6/run_ops_observability_check.sh`
  - cron wrapper:
    - `<server-repo-root>/scripts/phase6/run_ops_observability_cron.sh`
- Optional uptime alert env:
  - `RECALL_UPTIME_ALERT_WEBHOOK_URL`
  - `RECALL_UPTIME_ALERT_TELEGRAM_BOT_TOKEN`
  - `RECALL_UPTIME_ALERT_TELEGRAM_CHAT_ID`
  - `RECALL_UPTIME_NOTIFY_ON_SUCCESS`
- Optional OTEL / Honeycomb env:
  - `RECALL_OTEL_ENABLED`
  - `OTEL_SERVICE_NAME`
  - `OTEL_EXPORTER_OTLP_ENDPOINT`
  - `OTEL_EXPORTER_OTLP_HEADERS`
  - `HONEYCOMB_API_KEY`
  - `HONEYCOMB_DATASET`
  - `HONEYCOMB_API_ENDPOINT`
- Observability artifacts:
  - `<server-repo-root>/data/artifacts/observability`

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
- Generation retry controls (applies to Ollama + cloud providers):
  - `RECALL_GENERATE_RETRIES` (default `3`)
  - `RECALL_GENERATE_BACKOFF_SECONDS` (default `1.5`)

## n8n Ingestion Webhook

- Unified webhook endpoint (local on server): `http://localhost:5678/webhook/recall-ingest`
- Validation status: `HTTP 200` for test payload (verified 2026-02-22)
- Backing workflow:
  - Active: `qKMhxYULZoPwXnDI` (`Recall Ingest Webhook v2`)
  - Inactive legacy: `aOyMgFwit2mS82pP` (`Recall Ingest Webhook`)

## n8n Query Webhook (Workflow 02)

- Query webhook endpoint (local on server): `http://localhost:5678/webhook/recall-query`
- Backing bridge endpoint (server): `http://localhost:8090/v1/rag-queries`
- Validation status:
  - Bridge route: `HTTP 200` for dry-run query payload (verified 2026-02-22)
  - n8n production webhook: `HTTP 200` with cited RAG JSON payload (verified 2026-02-22)
- Deployment mode note:
  - n8n container does not include `python3`; `Execute Command`-based Workflow 02 fails with `/bin/sh: python3: not found`.
  - Use HTTP bridge workflow for Workflow 02 in this environment.

## Bridge API Controls (Phase 5A-5D)

- API identity: `operations-v1`
- Canonical base paths: `/v1/*`
- Shared config endpoint:
  - canonical: `GET /v1/auto-tag-rules`
- Canonical route policy:
  - canonical `/v1/*` endpoints are required for all clients, workflows, and docs.
  - compatibility aliases were removed during Phase `5F` canonical-only cutover.
- Canonical group model:
  - enum: `job-search|learning|project|reference|meeting`
  - fallback: invalid or missing group resolves to `reference`.
- Ingestion payload support:
  - `POST /v1/ingestions` accepts optional `group` and `tags`.
  - ingested chunk payloads persist `group`, `tags`, and `ingestion_channel` in Qdrant metadata.
  - `POST /v1/ingestions/files` accepts multipart file uploads (`.pdf`, `.docx`, `.txt`, `.md`, `.html`, `.eml`) plus optional `group`, `tags`, and `save_to_vault`.
  - upload size limit is controlled by `RECALL_MAX_UPLOAD_MB` (default `50`, returns `413` when exceeded).
- Query payload support:
  - `POST /v1/rag-queries` accepts optional `filter_group`, `filter_tags`, and `filter_tag_mode` (`any|all`).
  - `filter_tag_mode` aliases (`or|and`) normalize to canonical values (`any|all`).
  - invalid `filter_group` values normalize to `reference`.
  - invalid `filter_tag_mode` values return `HTTP 400`.
- Activity API support:
  - canonical: `GET /v1/activities`
  - query params:
    - `limit` (`1..200`, default `25`)
    - `group` (optional canonical group filter)
  - source table: `ingestion_log` with persisted `group_name` + `tags_json` columns.
- Eval API support:
  - canonical:
    - `GET /v1/evaluations` (`?latest=true` for newest summary)
    - `POST /v1/evaluation-runs`
  - run behavior:
    - `POST /v1/evaluation-runs` supports async queue mode (`wait=false`) and synchronous mode (`wait=true`) via `scripts/eval/run_eval.py`.
- Vault support:
  - canonical:
    - `GET /v1/vault-files`
    - `POST /v1/vault-syncs`
  - sync implementation path: `scripts/phase5/vault_sync.py`
  - wrappers:
    - `scripts/phase5/run_vault_sync_now.sh`
    - `scripts/phase5/run_vault_watch_now.sh`
  - runtime validation (ai-lab, 2026-02-24):
    - OpenAPI includes `/v1/vault-files` and `/v1/vault-syncs`.
    - `POST /v1/vault-syncs` dry-run with explicit `vault_path` returns `HTTP 200`.
    - before vault env+mount wiring, `GET /v1/vault-files` returned `400 validation_failed` (invalid default vault path).
    - after vault env+mount wiring, `GET /v1/vault-files` returns `HTTP 200` (empty tree when vault has no notes).
  - bridge container runtime env (ai-lab compose):
    - `RECALL_VAULT_PATH=<vault-root>`
    - `RECALL_VAULT_DEBOUNCE_SEC=5`
    - `RECALL_VAULT_EXCLUDE_DIRS=_attachments,.obsidian,.trash,recall-artifacts`
    - `RECALL_VAULT_WRITE_BACK=false`
  - bridge compose mount (ai-lab):
    - `<vault-root>:<vault-root>`
- Optional auth:
  - `RECALL_API_KEY` enforces `X-API-Key` header when set.
- Rate limiting env vars:
  - `RECALL_API_RATE_LIMIT_WINDOW_SECONDS` (default `60`)
  - `RECALL_API_RATE_LIMIT_MAX_REQUESTS` (default `120`)
- CORS env var:
  - `RECALL_API_CORS_ORIGINS` (default `*`, comma-separated origins supported)
- Vault env vars:
  - `RECALL_VAULT_PATH` (default `~/obsidian-vault`)
  - `RECALL_VAULT_SYNC_MODE` (default `watch`)
  - `RECALL_VAULT_DEBOUNCE_SEC` (default `5`)
  - `RECALL_VAULT_EXCLUDE_DIRS` (default `_attachments,.obsidian,.trash,recall-artifacts`)
  - `RECALL_VAULT_WRITE_BACK` (default `false`)
  - `RECALL_VAULT_IS_SYNCED` (default `true`)
- ai-lab host dependency note (watch mode):
  - `watchdog` required for `--watch` mode (`pip install watchdog`).
- Dashboard support:
  - canonical readiness route:
    - `GET /v1/dashboard-checks`
  - background cache warmer env:
    - `RECALL_DASHBOARD_CACHE_WARMER`
    - `RECALL_DASHBOARD_CACHE_WARM_INTERVAL_SECONDS`
  - Phase 6 cache env:
    - `RECALL_PHASE6_JOBS_CACHE_SECONDS`
    - `RECALL_PHASE6_COMPANY_CACHE_SECONDS`
    - `RECALL_PHASE6_GAP_CACHE_SECONDS`

## Execution Debug Rule (n8n)

- For webhook failures, inspect n8n `Executions` first and use failed node + error details as source of truth before changing workflow wiring.

## Hostname/Port Scope Rule

- `localhost` always means the current machine/container.
- From MacBook, use `http://<ai-lab-tailnet-ip>:<port>` for ai-lab services.
- From ai-lab shell, use `http://localhost:<port>` for host-published services.

## Phase Status

- Phase 0: complete (all baseline checks and ingestion webhook validation done)
- Phase 1: complete (`1A`-`1D` done; Workflow 02 webhook live and eval suite passing)
- Phase 2: complete (`2A`-`2C` done; meeting pipeline + domain retrieval/evals operational)
- Phase 3: complete (`3A` operator wrappers/forms, `3B` retrieval-quality track, `3C` ops hardening + portfolio bundle validated on ai-lab on 2026-02-24)
- Phase 5: complete (`5A`-`5E.1` implementation complete and `5F` hardening/closeout validated, including canonical-only API cutover, coverage gate, operator entrypoint, demo runner evidence, auth/rate-limit verification, and completion checklist closure on 2026-02-26)
- Phase 6A: complete (foundation routes live on ai-lab, `recall_jobs`/`recall_resume` created, resume version `2` ingested from `<vault-root>/career/Jay-Dreyer-Resume.md`, and Daily Dashboard serving on port `3001` as of 2026-03-04)
- Phase 6B: complete (job discovery runner, n8n workflow exports, and OpenAI Ashby migration shipped and validated on ai-lab)
- Phase 6C: complete (evaluation, Telegram notification, observation telemetry, and Workflow 3 runtime path validated on ai-lab)
- Phase 6D: complete (daily dashboard implementation, deploy validation, cache warming, recovery UX, and operator smoke path live on ai-lab)

## Skills Baseline (local Codex)

- Newly added in this setup pass:
  - `jupyter-notebook`
  - `transcribe`
  - `spreadsheet`
  - `security-ownership-map`

## Update Rule

Whenever services, ports, paths, provider config, or deployment topology changes, update this file in the same commit.
