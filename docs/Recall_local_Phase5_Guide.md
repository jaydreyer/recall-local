# Recall.local - Phase 5 Guide

Purpose: convert the current operator-heavy system into a frictionless daily-use product with dashboard UI, Chrome capture, Obsidian sync, and production guardrails.

Source inputs:
- `/Users/jaydreyer/projects/recall-local/docs/phase5-implementation-brief.md`
- `/Users/jaydreyer/projects/recall-local/docs/scaffolds/recall-dashboard.jsx`
- `/Users/jaydreyer/projects/recall-local/docs/scaffolds/recall-chrome-popup.jsx`

## Phase 5 goal

Ship a demo-ready and daily-usable Recall.local where ingestion is low-friction (dashboard + extension + Obsidian), querying is self-serve, and bridge operations are protected by auth/tests.

## Current baseline (start state)

1. Bridge API exists at `scripts/phase1/ingest_bridge_api.py` with:
   - `POST /ingest/{webhook|bookmarklet|ios-share|gmail-forward}`
   - `POST /query/rag`
   - `POST /meeting/action-items`
2. n8n workflows and bridge path are operational for ingestion/query/meeting pipelines.
3. Phase 4 telemetry and CI scaffolding are in place but soak thresholds are currently red.
4. No dedicated dashboard app, Chrome extension, or Obsidian sync implementation exists yet.

## Confirmed decisions (2026-02-24)

1. FastAPI migration is approved and is the first implementation task in Phase 5.
2. Dashboard deploys as a separate `recall-ui` container (static Vite build via nginx).
3. Obsidian write-back is opt-in:
   - `RECALL_VAULT_WRITE_BACK=false` by default in `.env.example`.
4. Chrome Gmail content script is deferred to `5E.1` after extension base stability.
5. Auth policy is optional local mode:
   - if `RECALL_API_KEY` unset: no auth enforcement and startup warning is logged.
   - if `RECALL_API_KEY` set: enforce `X-API-Key`.
6. Obsidian deployment model is Mac-primary vault with Syncthing mirror on ai-lab.

## Phase 5 sub-phases

| Sub-phase | Scope | Exit criteria |
|---|---|---|
| `5A` Bridge API platform layer | FastAPI migration, API key auth, rate limiting, shared config endpoint, endpoint contracts for UI/extension/Obsidian. | Bridge endpoints needed by UI/extension return deterministic JSON and are protected when key is configured. |
| `5B` Ingestion metadata + group/tag model | Add first-class `group` + enriched tags across ingestion and retrieval payloads. | Ingested chunks carry stable `group`, `tags`, and source metadata; filter queries work end-to-end. |
| `5C` Obsidian integration | Vault one-shot + watcher sync, metadata extraction, optional write-back artifacts. | Vault notes can be synced on demand with dedupe/change detection and queried with source attribution. |
| `5D` Dashboard UI | React dashboard with Ingest, Query, Activity, Eval, Vault tabs using bridge endpoints. | Operator can ingest/query/monitor from one UI without curl/n8n payload editing. |
| `5E` Chrome extension | Popup, context menu, keyboard shortcut, auto-tagging base experience. | User can capture current page/selection in <= 2 clicks with auto group/tag defaults. |
| `5E.1` Chrome Gmail assist (deferred) | Content script injection and sender-aware prefill for Gmail. | Gmail capture works without regressing base extension stability. |
| `5F` Final hardening + demo packaging | Tests, compose consolidation, retry parity, polish docs/demo script. | Reproducible demo run and CI gate with sufficient unit coverage and runbook completeness. |

## Architecture decisions for Phase 5

1. Migrate current `http.server` bridge to FastAPI before adding new Phase 5 endpoints.
2. Use a separate React/Vite frontend for dashboard in its own container.
3. Shared auto-tag config remains single-source JSON:
   - `config/auto_tag_rules.json`
   - served by bridge `GET /v1/auto-tag-rules` (compatibility alias: `GET /config/auto-tags`)
4. Obsidian sync excludes:
   - `.obsidian`
   - `.trash`
   - `_attachments`
   - `recall-artifacts` (prevents ingestion feedback loop)
5. API auth model:
   - if `RECALL_API_KEY` is empty: local/trusted mode with startup warning
   - if set: require `X-API-Key` on extension/dashboard calls
6. Extension Gmail integration is explicitly deferred until base extension quality gate is met.

## Endpoint plan (bridge)

API identity: `operations-v1` (major-versioned API surface; canonical endpoints are under `/v1`).

### Existing endpoints (canonical + compatibility aliases)

Canonical REST endpoints:
1. `POST /v1/ingestions`
2. `POST /v1/rag-queries`
3. `POST /v1/meeting-action-items`
4. `GET /v1/healthz`

Compatibility aliases (kept for backward compatibility, hidden from OpenAPI docs):
1. `POST /ingest/{webhook|bookmarklet|ios-share|gmail-forward}`
2. `POST /query/rag`
3. `POST /rag/query`
4. `POST /meeting/action-items`
5. `POST /meeting/actions`
6. `POST /query/meeting`

### New endpoints (Phase 5)

1. `GET /v1/auto-tag-rules` (compatibility alias: `GET /config/auto-tags`)
2. `POST /ingest/url`
3. `POST /ingest/text`
4. `POST /ingest/gdoc`
5. `POST /ingest/email`
6. `POST /ingest/file` (multipart upload)
7. `GET /activity` (`?group=` optional filter)
8. `GET /eval/latest`
9. `POST /eval/run`
10. `GET /vault/tree`
11. `POST /vault/sync`

## Data contract updates (ingestion + retrieval)

Required metadata fields on ingested chunks:

1. `group` (`job-search|learning|project|reference|meeting`, default `reference`)
2. `tags` (existing)
3. `source_type` (existing)
4. `source` / `source_ref` (existing pattern)
5. `ingestion_channel` (existing pattern)
6. `vault_path` (Obsidian notes only)
7. `wiki_links` (Obsidian notes only)

Retrieval/query behavior:

1. Preserve existing `filter_tags`.
2. Add optional `filter_group` for dashboard/extension scoped queries.
3. Keep `mode` routing intact (`default|job-search|learning`).

## Obsidian implementation plan

### Components

1. `scripts/phase5/vault_sync.py`
2. Optional wrappers:
   - `scripts/phase5/run_vault_sync_now.sh`
   - `scripts/phase5/run_vault_watch_now.sh`
3. Optional write-back helper for query/eval artifacts into `recall-artifacts/`.

### Deployment model

1. Primary vault on Mac (`~/obsidian-vault`).
2. Syncthing mirror on ai-lab (`~/obsidian-vault` on server side).
3. `vault_sync.py` runs on ai-lab against mirrored path.
4. Watcher must handle Syncthing temp-to-final rename behavior (`on_moved` events).

### Minimum v1 behavior

1. One-shot sync scans vault for `.md` files and ingests changed files only.
2. Hash-based dedupe state stored in a lightweight SQLite file under `data/`.
3. Group inferred from folder mapping in `config/auto_tag_rules.json`.
4. Extract `[[wiki-links]]`, hashtag tags, and frontmatter fields.
5. Exclude Syncthing transient files (`.syncthing.*`, `.tmp`) from ingestion.
6. Write-back remains disabled unless explicitly enabled.

## Dashboard implementation plan

### App layout

1. React + Vite app under `ui/dashboard/`
2. Tabs:
   - Ingest
   - Query
   - Activity
   - Eval
   - Vault
3. Color/group system follows scaffold and shared auto-tag config.

### Integration

1. Base API URL from env (default `http://localhost:8090`).
2. Optional API key header from env/local storage.
3. Dashboard is read-write client only; bridge remains the execution backend.
4. UI is deployed as separate `recall-ui` container.

## Chrome extension plan

### v1 feature set

1. Popup with auto-detected group/tags.
2. Context menu: page/link/selection to Recall.
3. Keyboard shortcut to open popup.
4. Config and API key stored in `chrome.storage.local`.

### v1.1 feature set (deferred)

1. Gmail helper script for extracting subject/sender/body.
2. Reuse popup flow for confirmation/override.

## Production hardening scope

1. Auth + rate limiting on bridge (Phase 5A).
2. Pytest suite target: 25-30 tests with mocks.
3. Docker compose consolidation into a single operator entrypoint.
4. Cloud provider retry parity in `scripts/llm_client.py`.

## Environment additions (Phase 5)

1. `RECALL_API_KEY=`
2. `RECALL_API_RATE_LIMIT_WINDOW_SECONDS=60`
3. `RECALL_API_RATE_LIMIT_MAX_REQUESTS=120`
4. `RECALL_VAULT_PATH=~/obsidian-vault`
5. `RECALL_VAULT_SYNC_MODE=watch`
6. `RECALL_VAULT_DEBOUNCE_SEC=5`
7. `RECALL_VAULT_EXCLUDE_DIRS=_attachments,.obsidian,.trash,recall-artifacts`
8. `RECALL_VAULT_WRITE_BACK=false`
9. `RECALL_VAULT_IS_SYNCED=true`

## Recommended implementation order

1. FastAPI migration (replace `http.server` bridge implementation).
2. API key auth + startup warning behavior.
3. Rate limiting middleware.
4. Auto-tag rules config (`config/auto_tag_rules.json`) + `GET /v1/auto-tag-rules` (keep `GET /config/auto-tags` alias).
5. Pytest scaffolding + target test coverage.
6. Docker compose consolidation (including separate `recall-ui` container).
7. New bridge endpoints (`ingest/file`, `activity`, `eval`, `vault`, `config`).
8. Group/tag support in ingestion and query contracts.
9. Obsidian sync (`--once` + `--watch`) with Syncthing event handling.
10. Obsidian metadata extraction (`wiki-links`, hashtags, frontmatter).
11. Recall -> Vault write-back (opt-in only).
12. Dashboard UI implementation (5 tabs).
13. Chrome extension base (`popup`, `context menu`, `shortcut`).
14. Cloud provider retry parity.
15. Demo packaging + README polish.
16. `5E.1` Gmail content script after base extension stabilization.

## Acceptance gate

Phase 5 is complete when all are true:

1. User can ingest URL/text/file/email/Obsidian note without manual payload crafting.
2. User can query from dashboard and receive cited sources with group/tag filtering.
3. Chrome capture flow is <=2 clicks for common web pages.
4. Vault sync is repeatable and excludes feedback-loop directories.
5. Bridge auth/rate limiting and CI tests provide deterministic pass/fail behavior.
