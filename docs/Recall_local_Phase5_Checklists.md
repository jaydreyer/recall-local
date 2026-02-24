# Recall.local - Phase 5 Checklists

Source plan: `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase5_Guide.md`

## 5A. Bridge Platform Layer

- [x] Migrate bridge from `http.server` to FastAPI before adding new Phase 5 endpoints.
- [x] Add API key validation helper in bridge (`X-API-Key` when configured).
- [x] Add startup warning when `RECALL_API_KEY` is unset (local unauthenticated mode).
- [x] Add rate limiter with configurable window/limit env vars.
- [x] Add auto-tag rules endpoint (`GET /v1/auto-tag-rules`) with compatibility alias `GET /config/auto-tags`, serving `config/auto_tag_rules.json`.
- [x] Add endpoint contract tests for auth success/failure and rate-limit behavior.
- [x] Document new env vars in `docker/.env.example`.

## 5B. Group/Tag Metadata Model

- [ ] Define canonical group enum and default handling (`reference` fallback).
- [ ] Extend ingest endpoint payloads to accept `group` + `tags`.
- [ ] Ensure chunk metadata stores `group`, `tags`, and `ingestion_channel`.
- [ ] Add query option `filter_group` and validate bridge payload parsing.
- [ ] Add regression tests for metadata propagation and filtering.

## 5C. Obsidian Integration

- [ ] Implement one-shot vault sync (`--once`) with hash-based change detection.
- [ ] Implement watch mode (`--watch`) with debounce window.
- [ ] Exclude `.obsidian`, `.trash`, `_attachments`, and `recall-artifacts`.
- [ ] Exclude Syncthing temp files (`.syncthing.*` and `.tmp`).
- [ ] Handle Syncthing rename flow via `on_moved` event handling.
- [ ] Derive group from folder mapping in `config/auto_tag_rules.json`.
- [ ] Parse Obsidian metadata:
  - [ ] `[[wiki-links]]`
  - [ ] hashtag tags
  - [ ] frontmatter
- [ ] Add optional write-back for Recall artifacts to `recall-artifacts/` (default disabled).
- [ ] Add bridge endpoints:
  - [ ] `GET /vault/tree`
  - [ ] `POST /vault/sync`
- [ ] Add tests for changed-file detection and excluded-path behavior.
- [ ] Document Mac-primary + Syncthing mirror setup for ai-lab watcher deployment.

## 5D. Dashboard UI

- [ ] Scaffold React/Vite dashboard under `ui/dashboard/`.
- [ ] Implement tabs:
  - [ ] Ingest
  - [ ] Query
  - [ ] Activity
  - [ ] Eval
  - [ ] Vault
- [ ] Wire ingestion actions to new bridge endpoints.
- [ ] Wire query panel to `POST /v1/rag-queries` with mode/group/tag controls.
- [ ] Wire Activity tab to `GET /activity`.
- [ ] Wire Eval tab to `GET /eval/latest` + `POST /eval/run`.
- [ ] Wire Vault tab to `GET /vault/tree` + `POST /vault/sync`.
- [ ] Add API key + base URL settings handling.
- [ ] Deploy as separate `recall-ui` container (nginx static hosting).

## 5E. Chrome Extension

- [ ] Create `chrome-extension/` Manifest V3 scaffold.
- [ ] Build popup UI with group/tag auto-detect from shared config endpoint.
- [ ] Add context menu ingest for page/link/selection.
- [ ] Add keyboard shortcut (`Ctrl+Shift+R` equivalent command mapping).
- [ ] Add extension config storage (`api_base_url`, `api_key`).
- [ ] Validate extension flow against auth-enabled bridge.

## 5E.1. Chrome Gmail Content Script (Deferred)

- [ ] Add Gmail DOM injection content script once base extension is stable.
- [ ] Add sender-aware prefill using `email_senders` auto-tag rules.
- [ ] Validate DOM-change resilience and fallback behavior.

## 5F. Final Hardening + Demo Readiness

- [ ] Reach target coverage depth (25-30 tests, mocked external services).
- [ ] Consolidate compose runtime entrypoint for operator usage.
- [ ] Add cloud provider retry parity in LLM client layer.
- [ ] Update docs index + runbooks for new Phase 5 flows.
- [ ] Record demo run script covering:
  - [ ] dashboard ingest/query
  - [ ] extension capture
  - [ ] Obsidian sync/query
  - [ ] eval gate check

## Completion Checklist

- [ ] Frictionless ingest demonstrated from:
  - [ ] dashboard
  - [ ] chrome extension
  - [ ] obsidian vault
- [ ] Query UX is self-serve and citation-rich without curl.
- [ ] Auth/rate-limit controls verified in enabled mode.
- [ ] Phase 5 implementation log and environment inventory updated.
