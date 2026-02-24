# Recall.local Dashboard (Phase 5D)

React/Vite dashboard for Recall.local operations, backed by the bridge API.

## Tabs

- Ingest: `POST /v1/ingestions` + vault sync shortcut.
- Query: `POST /v1/rag-queries`.
- Activity: `GET /v1/activities` (alias `GET /activity`).
- Eval: `GET /v1/evaluations?latest=true` + `POST /v1/evaluation-runs` (aliases `/v1/evaluations/latest`, `/eval/latest`, `/eval/run`).
- Vault: `GET /v1/vault-files` + `POST /v1/vault-syncs`.

## Local development

```bash
npm install
npm run dev
```

Defaults to bridge API at `http://localhost:8090`.

## Build

```bash
npm run build
npm run preview
```

## Container

Build and run as `recall-ui` via `/Users/jaydreyer/projects/recall-local/docker/docker-compose.yml`.
