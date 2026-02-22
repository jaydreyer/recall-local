# Recall.local Implementation Log

## 2026-02-22 - Unified ingestion webhook verified on n8n

### Goal

- Satisfy Phase 0 criterion: unified ingestion webhook accepts a test payload.

### Actions performed on `ai-lab`

- Verified that `POST /webhook/recall-ingest` initially returned 404 because the webhook route was not registered.
- Imported a minimal n8n workflow with:
  - Webhook trigger (`POST`, path `recall-ingest`)
  - Code node response/ack payload
- Activated/published workflow and restarted n8n to load production webhook routes.
- Re-ran webhook test payload against local n8n endpoint.

### Result

- Webhook endpoint now responds successfully:
  - Endpoint: `http://localhost:5678/webhook/recall-ingest`
  - Result: `HTTP 200`
  - Sample response body: JSON ack with `received=true`

### Notes

- n8n instance is configured with:
  - `N8N_PATH=/n8n/`
  - `N8N_BASIC_AUTH_ACTIVE=true`
- Production webhook registration is on `/webhook/...` for local direct calls.
- Two Recall webhook workflows exist in DB history:
  - `aOyMgFwit2mS82pP` (`Recall Ingest Webhook`) inactive
  - `qKMhxYULZoPwXnDI` (`Recall Ingest Webhook v2`) active

## 2026-02-21 - Cloud provider validation and Gemini model update

### What was executed

- Ran provider checks on `ai-lab` (`/home/jaydreyer/recall-local`):
  - `RECALL_LLM_PROVIDER=anthropic python3 scripts/llm_client.py`
  - `RECALL_LLM_PROVIDER=openai python3 scripts/llm_client.py`
  - `RECALL_LLM_PROVIDER=gemini python3 scripts/llm_client.py`

### Results

- Anthropic: pass
- OpenAI: pass
- Gemini: initial fail with `404 Not Found` for `gemini-2.0-flash`

### Root cause and fix

- Gemini API response indicated `models/gemini-2.0-flash` is unavailable for new users.
- Updated default Gemini model to a currently available model:
  - `GEMINI_MODEL=gemini-2.5-flash`
- Updated client request to send Gemini API key in `x-goog-api-key` header instead of query string to reduce risk of key leakage in exception URLs.

### Files changed

- `docker/.env.example`
- `scripts/llm_client.py`

## 2026-02-21 - Project bootstrap, repo setup, and Phase 0 baseline

### Scope

- Read and confirmed project direction from:
  - `docs/Recall_local_PRD.md`
  - `docs/Recall_local_Phase0_Guide.md`
- Chose **Phase 0 Approach B** (add missing Recall.local pieces without disrupting existing running services).

### GitHub and Repo Actions

- Created GitHub repo: [jaydreyer/recall-local](https://github.com/jaydreyer/recall-local)
- Repo visibility set to `PRIVATE`.
- Added PRD and Phase 0 guide to the repo.

### Skills and Agents Installed (local Codex environment)

- Installed additional skills:
  - `jupyter-notebook`
  - `transcribe`
  - `spreadsheet`
  - `security-ownership-map`
- Existing relevant skills already present:
  - `openai-docs`, `playwright`, `pdf`, `doc`, `sentry`, `security-best-practices`, `security-threat-model`, `gh-*`, `screenshot`, `vercel-deploy`
- Each installed skill includes its `agents/` bundle.

### Phase 0 Files Added/Updated

- `docker/docker-compose.yml`
- `docker/.env.example`
- `docs/mkdocs.yml`
- `docs/docs/index.md`
- `docs/docs/artifacts/meetings/index.md`
- `docs/docs/artifacts/evals/index.md`
- `docs/docs/artifacts/ingestion/index.md`
- `requirements.txt`
- `scripts/llm_client.py`
- `scripts/phase0/setup_phase0.sh`
- `scripts/phase0/bootstrap_sqlite.py`
- `scripts/phase0/bootstrap_qdrant.py`
- `scripts/phase0/connectivity_check.py`

### Server Work Completed (`ai-lab`)

- Host access stabilized through Tailscale:
  - Hostname: `ai-lab`
  - Tailscale IP: `100.116.103.78`
  - User: `jaydreyer`
- Synced repo to server path:
  - `/home/jaydreyer/recall-local`
- Ran Phase 0 setup script.
- Because `python3-venv` is not installed and no sudo path was available from session, used user-site fallback install path in setup script.
- Initialized SQLite:
  - `/home/jaydreyer/recall-local/data/recall.db`
  - tables: `runs`, `eval_results`, `alerts`, `ingestion_log`
- Created/verified Qdrant collection:
  - `recall_docs`
  - vector dimension `768`
- Started artifact viewer:
  - container: `recall-mkdocs`
  - URL: `http://100.116.103.78:8100/` (Tailnet access)
- Smoke test result:
  - `8/8` checks passed (`scripts/phase0/connectivity_check.py`)

### Provider Status

- Confirmed local provider works:
  - `RECALL_LLM_PROVIDER=ollama python3 scripts/llm_client.py` succeeded.
- Cloud provider keys remain placeholders in:
  - `/home/jaydreyer/recall-local/docker/.env`

### Commits Created

- `0517c07` Add PRD and Phase 0 setup guide
- `05ef291` Add Phase 0 setup scaffolding and bootstrap scripts
- `b0245ff` Harden Phase 0 setup for no-root Ubuntu hosts

### Follow-ups

- Add real API keys for Anthropic/OpenAI/Gemini in server `docker/.env`.
- Run provider validation for cloud fallback.
- Optional: install `python3-venv` on server later to use isolated `.venv` path instead of user-site fallback.
