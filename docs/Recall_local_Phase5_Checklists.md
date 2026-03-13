# Recall.local - Phase 5 Checklists

Source plan: `<repo-root>/docs/Recall_local_Phase5_Guide.md`

## 5A. Bridge Platform Layer

- [x] Migrate bridge from `http.server` to FastAPI before adding new Phase 5 endpoints.
- [x] Add API key validation helper in bridge (`X-API-Key` when configured).
- [x] Add startup warning when `RECALL_API_KEY` is unset (local unauthenticated mode).
- [x] Add rate limiter with configurable window/limit env vars.
- [x] Add auto-tag rules endpoint (`GET /v1/auto-tag-rules`) with compatibility alias `GET /config/auto-tags`, serving `config/auto_tag_rules.json`.
- [x] Add endpoint contract tests for auth success/failure and rate-limit behavior.
- [x] Document new env vars in `docker/.env.example`.

## 5B. Group/Tag Metadata Model

- [x] Define canonical group enum and default handling (`reference` fallback).
- [x] Extend ingest endpoint payloads to accept `group` + `tags`.
- [x] Ensure chunk metadata stores `group`, `tags`, and `ingestion_channel`.
- [x] Add query option `filter_group` and validate bridge payload parsing.
- [x] Add regression tests for metadata propagation and filtering.

## 5C. Obsidian Integration

- [x] Implement one-shot vault sync (`--once`) with hash-based change detection.
- [x] Implement watch mode (`--watch`) with debounce window.
- [x] Exclude `.obsidian`, `.trash`, `_attachments`, and `recall-artifacts`.
- [x] Exclude Syncthing temp files (`.syncthing.*` and `.tmp`).
- [x] Handle Syncthing rename flow via `on_moved` event handling.
- [x] Derive group from folder mapping in `config/auto_tag_rules.json`.
- [x] Parse Obsidian metadata:
  - [x] `[[wiki-links]]`
  - [x] hashtag tags
  - [x] frontmatter
- [x] Add optional write-back for Recall artifacts to `recall-artifacts/` (default disabled).
- [x] Add bridge endpoints:
  - [x] canonical: `GET /v1/vault-files`, `POST /v1/vault-syncs`
  - [x] compatibility aliases: `GET /v1/vault/tree`, `POST /v1/vault/sync` (also unversioned `/vault/*`)
- [x] Add tests for changed-file detection and excluded-path behavior.
- [x] Document Mac-primary + Syncthing mirror setup for ai-lab watcher deployment.

## 5D. Dashboard UI

- [x] Scaffold React/Vite dashboard under `ui/dashboard/`.
- [x] Implement tabs:
  - [x] Ingest
  - [x] Query
  - [x] Activity
  - [x] Eval
  - [x] Vault
- [x] Wire ingestion actions to bridge ingestion/vault endpoints.
- [x] Wire query panel to `POST /v1/rag-queries` with mode/group/tag controls.
- [x] Wire Activity tab to canonical `GET /v1/activities` (compatibility alias: `GET /activity`).
- [x] Wire Eval tab to canonical `GET /v1/evaluations?latest=true` + `POST /v1/evaluation-runs` (compatibility aliases: `/v1/evaluations/latest`, `/eval/latest`, `/eval/run`).
- [x] Wire Vault tab to canonical `GET /v1/vault-files` + `POST /v1/vault-syncs` (compatibility aliases: `/vault/tree`, `/vault/sync`).
- [x] Add API key + base URL settings handling.
- [x] Deploy as separate `recall-ui` container (nginx static hosting).

## 5E. Chrome Extension

- [x] Create `chrome-extension/` Manifest V3 scaffold.
- [x] Build popup UI with group/tag auto-detect from shared config endpoint.
- [x] Add context menu ingest for page/link/selection.
- [x] Add keyboard shortcut (`Ctrl+Shift+R` equivalent command mapping).
- [x] Add extension config storage (`api_base_url`, `api_key`).
- [x] Validate extension flow against auth-enabled bridge.

## 5E.1. Chrome Gmail Content Script

- [x] Add Gmail DOM injection content script once base extension is stable.
- [x] Add sender-aware prefill using `email_senders` auto-tag rules.
- [x] Validate DOM-change resilience and fallback behavior.

## 5F. Final Hardening + Demo Readiness

- [x] Reach target coverage depth (25-30 tests, mocked external services).
- [x] Consolidate compose runtime entrypoint for operator usage.
- [x] Add cloud provider retry parity in LLM client layer.
- [x] Canonical-only API cutover (deferred): migrate remaining n8n/script callers from compatibility aliases to canonical `/v1/*` routes.
- [x] Canonical-only API cutover (deferred): remove compatibility alias routes from bridge after caller migration is verified.
- [x] Update docs index + runbooks for new Phase 5 flows.
- [x] Record demo run script covering:
  - [x] dashboard ingest/query
  - [x] extension capture
  - [x] Obsidian sync/query
  - [x] eval gate check

## Completion Checklist

- [x] Frictionless ingest demonstrated from:
  - [x] dashboard
  - [x] chrome extension
  - [x] obsidian vault
- [x] Query UX is self-serve and citation-rich without curl.
- [x] Auth/rate-limit controls verified in enabled mode.
- [x] Phase 5 implementation log and environment inventory updated.

## Post-Audit Punch List (2026-02-26)

- [x] Add canonical multipart file upload endpoint (`POST /v1/ingestions/files`) with auth/rate limits + size/type validation.
- [x] Add dashboard ingest drag-drop/file-picker flow wired to `POST /v1/ingestions/files` with selected group/tags.
- [x] Add CI pytest execution step to `quality_checks.yml`.
- [x] Add extension popup `save_to_vault` toggle wired into ingest payload.
- [x] Promote full-stack compose to `docker/docker-compose.yml`; preserve Approach B as `docker/docker-compose.lite.yml`.
- [x] Switch dashboard mono font to IBM Plex Mono.
- [x] Verify canonical `/v1/*` route references in runtime JSON/JS/PY/YML callers.
