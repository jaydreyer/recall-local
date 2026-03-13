# Recall.local

Recall.local is a local-first AI operations system that combines document ingestion, cited RAG, job-search automation, and reviewer-friendly operational artifacts in one repo.

It is designed as a portfolio project for solutions engineering and applied AI roles: the goal is not only to ship working features, but to make the system explainable under code review and live walkthrough conditions.

## What Reviewers Should Look At First

- [Architecture overview](docs/Recall_local_Architecture_Diagram.md)
- [Design decisions and tradeoffs](docs/Recall_local_Design_Decisions.md)
- [API reference and OpenAPI guide](docs/Recall_local_API_Reference.md)
- [Implementation log](docs/IMPLEMENTATION_LOG.md)
- [Environment inventory](docs/ENVIRONMENT_INVENTORY.md)

## System Summary

The system is organized around a few core pieces:

- A FastAPI bridge in [scripts/phase1/ingest_bridge_api.py](scripts/phase1/ingest_bridge_api.py) that exposes ingestion, retrieval, evaluation, and job-search endpoints.
- Retrieval and ranking helpers in [scripts/phase1/retrieval.py](scripts/phase1/retrieval.py) that combine vector search with lightweight lexical reranking.
- A Phase 6 job-search and evaluation pipeline in [scripts/phase6/](scripts/phase6) for discovery, scoring, and dashboard-ready summaries.
- React dashboards in [ui/dashboard/](ui/dashboard) and [ui/daily-dashboard/](ui/daily-dashboard) for operator workflows and job triage.
- Operational wrappers, evals, and runbooks under [scripts/](scripts) and [docs/](docs).

## API Documentation

The FastAPI bridge already publishes interactive API documentation when the bridge is running:

- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`
- OpenAPI JSON: `GET /openapi.json`

By default in local development, those are available from `http://localhost:8090/docs`, `http://localhost:8090/redoc`, and `http://localhost:8090/openapi.json`.

The repo-level API guide is here:

- [Recall.local API reference](docs/Recall_local_API_Reference.md)

## Why This Project Is Structured This Way

The project intentionally favors a few design choices:

- Local-first runtime so privacy, latency tradeoffs, and self-hosting concerns are part of the story.
- Dual memory model so semantic retrieval and structured operational state can coexist.
- Thin API gateway so UIs, automations, and experiments share one contract.
- Artifact-driven operations so demos and debugging are grounded in saved evidence rather than claims.

The short version is documented here:

- [Recall.local design decisions](docs/Recall_local_Design_Decisions.md)

## Repository Map

- [docs/](docs): PRD, runbooks, architecture, implementation history, and reviewer-facing documentation
- [scripts/](scripts): bridge, ingestion, retrieval, evaluation, and operational helpers
- [tests/](tests): endpoint contract tests and focused regression coverage
- [docker/](docker): compose stack and runtime configuration
- [n8n/](n8n): workflow assets and runbooks
- [ui/](ui): operator dashboards

## Testing Strategy

The test suite is designed to show reviewer-facing engineering judgment, not just raw assertion count.

- FastAPI contract tests validate the shared backend surface used by dashboards and workflows.
- Retrieval, evaluation, storage, deduplication, and draft-generation helpers have focused regression tests around the highest-risk logic.
- Cross-phase flow coverage now includes an integration-style request path from the bridge to Phase 6 cover-letter generation.
- Shared pytest fixtures in [tests/conftest.py](tests/conftest.py) reduce repeated temp DB and vault setup.

Current local baseline:

- `182` passing tests
- `49.62%` measured coverage across `scripts/`
- CI enforces a minimum coverage floor via `pytest-cov`

Run locally with:

```bash
python3 -m pytest tests/ -q --cov=scripts --cov-report=term-missing
```

## Python Environment

The repo now separates runtime and development dependencies:

- [requirements.txt](requirements.txt): pinned runtime dependencies
- [requirements-dev.txt](requirements-dev.txt): pinned local tooling for tests, coverage, linting, and dependency audit
- `pyproject.toml`: modern project metadata plus a `dev` optional dependency group

Example local setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Dependency audit is enforced in CI with `pip-audit`.

If you are reviewing the project for maintainability, the highest-signal test files are:

- [tests/test_bridge_api_contract.py](tests/test_bridge_api_contract.py)
- [tests/test_phase1_phase6_cover_letter_flow_pytest.py](tests/test_phase1_phase6_cover_letter_flow_pytest.py)
- [tests/test_phase6c_evaluation_observation.py](tests/test_phase6c_evaluation_observation.py)
- [tests/test_phase6_storage_pytest.py](tests/test_phase6_storage_pytest.py)

## Current Status

The current canonical status docs are:

- [Implementation log](docs/IMPLEMENTATION_LOG.md)
- [Environment inventory](docs/ENVIRONMENT_INVENTORY.md)
- [Documentation index](docs/README.md)
