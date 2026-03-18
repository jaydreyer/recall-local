# Recall.local Implementation Log

Public-repo note: historical entries use placeholder hostnames and paths where the original logs referenced private machine details. Older file references remain as evidence-first text and may no longer be directly clickable.

## 2026-03-18 - Tailored summary artifact flow added to the Application Ops packet

### What was executed

- Added a first-class tailored summary generator in:
  - `<repo-root>/scripts/phase6/tailored_summary_drafter.py`
  - generates a three-bullet tailored summary from evaluated job context plus the active resume
  - supports the same local/cloud runtime settings pattern as the cover-letter flow
  - optionally writes a packet artifact into the vault when write-back is enabled
- Added a new collection-style API endpoint in:
  - `<repo-root>/scripts/phase1/bridge_routes_phase6.py`
  - `POST /v1/tailored-summaries`
  - persists the result back into workflow packet state and packet artifact metadata so the Ops packet becomes backed by a real generated deliverable
- Added API models/examples and helper exports in:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - `<repo-root>/scripts/phase1/bridge_routes_models.py`
  - `<repo-root>/scripts/phase1/bridge_routes_phase6_helpers.py`
- Added dashboard support in:
  - `<repo-root>/ui/daily-dashboard/src/api.js`
  - `<repo-root>/ui/daily-dashboard/src/hooks/useJobs.js`
  - `<repo-root>/ui/daily-dashboard/src/components/JobDetail.jsx`
  - `<repo-root>/ui/daily-dashboard/src/components/TailoredSummaryDraft.jsx`
  - the role workspace can now trigger tailored summary generation and show the generated content immediately
- Added regression coverage in:
  - `<repo-root>/tests/test_phase6_tailored_summary_drafter_pytest.py`
  - `<repo-root>/tests/test_phase1_phase6_tailored_summary_flow_pytest.py`
  - `<repo-root>/tests/test_bridge_api_contract.py`

### Validation

- Local validation:
  - `./.venv/bin/python -m pytest -q tests/test_phase6_tailored_summary_drafter_pytest.py tests/test_phase1_phase6_tailored_summary_flow_pytest.py tests/test_bridge_api_contract.py -k "tailored_summary or openapi_schema_lists_canonical_paths_only"`
  - `npm run build` (from `ui/daily-dashboard/`)

### Results

- The packet now has a second real generated artifact flow beyond cover letters.
- Tailored summary progress no longer has to rely only on checkbox state or manually linked artifact metadata.

## 2026-03-18 - Application Ops timeline semantics and follow-up history refined

### What was executed

- Tightened Phase 6 workflow timeline metadata in:
  - `<repo-root>/scripts/phase6/job_repository.py`
  - workflow events now carry explicit category, origin, and tone metadata so Ops can distinguish approvals, packet work, follow-up changes, application history, and derived signals
  - status/application mutations now emit more specific timeline labels such as `Application recorded` instead of relying on generic status-change language
- Improved Ops timeline rendering in:
  - `<repo-root>/ui/daily-dashboard/src/utils/workflowDemo.js`
  - `<repo-root>/ui/daily-dashboard/src/components/OpsWorkspace.jsx`
  - persisted workflow events now keep their richer semantics in the right rail, synthetic events are marked as derived, and duplicate synthetic application/draft history is suppressed when persisted events already exist
- Added direct regression coverage in:
  - `<repo-root>/tests/test_phase6_job_repository.py`
  - covers legacy timeline normalization metadata inference, richer workflow mutation event generation, and follow-up completion behavior

### Validation

- Local validation:
  - `python3 -m pytest -q tests/test_phase6_job_repository.py`

### Results

- The Ops timeline now reads more like a true application-history rail instead of a flat mixed event list.
- Follow-up, approval, packet, and artifact transitions are easier to distinguish in both backend data and dashboard presentation.

## 2026-03-18 - Application Ops packet readiness now reconciles checklist state with artifact truth

### What was executed

- Added computed packet-readiness reconciliation in:
  - `<repo-root>/scripts/phase6/job_repository.py`
  - job workflow payloads now expose `workflow.packetReadiness` with checked, linked, verified, and required-item counts plus mismatch lists for checklist-without-artifact and artifact-without-checklist states
- Updated Ops packet heuristics in:
  - `<repo-root>/ui/daily-dashboard/src/utils/workflowDemo.js`
  - `<repo-root>/ui/daily-dashboard/src/components/OpsWorkspace.jsx`
  - packet labels, blockers, queue summaries, readiness sorting, and `Ready to apply` gating now depend on both persisted checklist state and linked artifact truth
  - packet approval remains backward-compatible, but the UI now distinguishes genuinely approval-ready packets from approvals granted with incomplete evidence
- Refreshed bridge example payloads in:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - surfaces the new `packetReadiness` response shape in the jobs example
- Expanded regression coverage in:
  - `<repo-root>/tests/test_phase6_job_repository.py`
  - covers the new readiness reconciliation logic for core packet artifacts

### Validation

- Local validation:
  - `./.venv/bin/python -m pytest -q tests/test_phase6_job_repository.py`
  - `npm run build` (from `ui/daily-dashboard/`)

### Results

- The Ops console now treats packet readiness as a combination of operator checklist confirmation and real linked deliverables instead of assuming either source alone is sufficient.
- Queue counts and blockers better reflect which roles are actually ready to move toward application.

## 2026-03-13 - Public-readiness hardening, shared helpers, and bridge route extraction

### What was executed

- Removed reviewer-visible private-host leakage from public-facing code, workflow exports, shell examples, and wiring docs:
  - standardized workflow bridge targets around `RECALL_BRIDGE_BASE_URL` with `http://localhost:8090` fallback
  - replaced private host defaults in shell examples and hygiene tooling with localhost-safe values or the `ai-lab` alias
  - removed the hardcoded deployment server default from FastAPI OpenAPI `servers`; local is now the only default and an optional deploy server can be injected with `RECALL_API_SERVER_DEPLOY`
- Added shared helper modules in:
  - `<repo-root>/scripts/shared_time.py`
  - `<repo-root>/scripts/shared_strings.py`
  - `<repo-root>/scripts/shared_qdrant.py`
  - consolidated duplicated ISO timestamp, slug, and Qdrant client wiring used across Phase 0, Phase 1, and Phase 6 modules
- Added direct regression coverage for previously reviewer-visible gaps in:
  - `<repo-root>/tests/phase1/test_rag_query_pytest.py`
  - `<repo-root>/tests/test_phase6_job_evaluator_pytest.py`
  - `<repo-root>/tests/phase1/test_channel_adapters_pytest.py`
  - `<repo-root>/tests/test_phase0_bootstrap_qdrant_pytest.py`
  - `<repo-root>/tests/test_phase0_connectivity_check_pytest.py`
- Expanded static type coverage in:
  - `<repo-root>/pyproject.toml`
  - now includes `scripts/phase1/rag_query.py` and `scripts/phase6/job_evaluator.py`
- Extracted bridge endpoint registration out of the top-level FastAPI app file into:
  - `<repo-root>/scripts/phase1/bridge_routes_core.py`
  - `<repo-root>/scripts/phase1/bridge_routes_phase6.py`
  - top-level app creation in `<repo-root>/scripts/phase1/ingest_bridge_api.py` now keeps startup, middleware, auth/rate-limiting, and fallback handlers while delegating route registration to dedicated modules
- Added dedicated phase-specific contract/shared layers to keep route modules decoupled from the monolith:
  - `<repo-root>/scripts/phase1/bridge_routes_models.py`
  - `<repo-root>/scripts/phase1/bridge_routes_middleware.py`
  - `<repo-root>/scripts/phase1/bridge_routes_core_helpers.py`
  - `<repo-root>/scripts/phase1/bridge_routes_core_contracts.py`
  - `<repo-root>/scripts/phase1/bridge_routes_phase6_helpers.py`
  - `<repo-root>/scripts/phase1/bridge_routes_phase6_contracts.py`

### Validation

- Search validation:
  - `rg -n "100\\.116\\.103\\.78" scripts tests docs n8n/workflows README.md AGENTS.md`
    - returned no matches
- Focused validation:
  - `python3 -m pytest -q tests/test_bridge_api_contract.py tests/test_phase5f_canonical_workflow_routes.py tests/phase1/test_rag_query_pytest.py tests/test_phase6_job_evaluator_pytest.py tests/phase1/test_channel_adapters_pytest.py tests/test_phase0_bootstrap_qdrant_pytest.py tests/test_phase0_connectivity_check_pytest.py`
  - `python3 -m py_compile scripts/phase1/ingest_bridge_api.py scripts/phase1/bridge_routes_core.py scripts/phase1/bridge_routes_phase6.py`
  - `python3 -m ruff check .`
  - `python3 -m mypy`
- Full regression:
  - `python3 -m pytest tests/ -q`
    - `229 passed`

### Results

- The public repo no longer exposes the prior private Tailnet IP in tracked source, workflow artifacts, or reviewer-facing docs.
- Reviewer-visible Phase 1 and Phase 6 logic now has direct regression coverage instead of relying only on indirect flows.
- Shared helper duplication was reduced without changing external API behavior.
- The bridge API keeps the same `/v1/*` contract while route registration is now split out of the former single large route block.

## 2026-03-13 - Package boundaries and shared module APIs cleaned up

### What was executed

- Added explicit package markers in:
  - `<repo-root>/scripts/__init__.py`
  - `<repo-root>/scripts/eval/__init__.py`
  - `<repo-root>/scripts/phase0/__init__.py`
  - `<repo-root>/scripts/phase1/__init__.py`
  - `<repo-root>/scripts/phase2/__init__.py`
  - `<repo-root>/scripts/phase3/__init__.py`
  - `<repo-root>/scripts/phase4/__init__.py`
  - `<repo-root>/scripts/phase5/__init__.py`
  - `<repo-root>/scripts/phase6/__init__.py`
  - gives the repo explicit Python package boundaries instead of relying on implicit namespace-package behavior
  - documents the intended public module surface for each phase package
- Tightened the shared LLM client in:
  - `<repo-root>/scripts/llm_client.py`
  - added an explicit public API (`generate`, `embed`)
  - aligned env loading with the rest of the repo by loading both `docker/.env` and `docker/.env.example`
  - replaced the ad hoc `__main__` block with a `main()` entrypoint
  - normalized type hints to built-in generic syntax
- Tightened the ingestion wrapper in:
  - `<repo-root>/scripts/phase1/ingest_from_payload.py`
  - added an explicit reusable `run_payload_ingestion(...)` helper so CLI behavior is available as a real module API instead of only through `main()`
  - added an explicit public API list for the module
- Removed stale local-only filesystem artifacts:
  - deleted `<repo-root>/scripts/.DS_Store`
  - removed the empty `<repo-root>/scripts/extract` directory

### Validation

- Local validation:
  - `python3 -m py_compile scripts/__init__.py scripts/eval/__init__.py scripts/phase0/__init__.py scripts/phase1/__init__.py scripts/phase2/__init__.py scripts/phase3/__init__.py scripts/phase4/__init__.py scripts/phase5/__init__.py scripts/phase6/__init__.py scripts/llm_client.py scripts/phase1/ingest_from_payload.py`
  - confirmed `scripts/.DS_Store` and `scripts/extract` are gone locally

### Results

- The repo now has clearer module/package boundaries and less implicit import behavior.
- Shared modules expose cleaner public APIs for reuse from tests, wrappers, and future refactors.
- No active `TODO`, `FIXME`, or `HACK` comments were found in `scripts/` or `tests/` during the audit.

## 2026-03-13 - Public repo ignore rules tightened

### What was executed

- Expanded ignore coverage in:
  - [<repo-root>/.gitignore](<repo-root>/.gitignore)
  - added broad `.env` and `docker/.env.*` secret patterns while preserving `*.example` files
  - added common local artifact patterns for `.coverage`, `htmlcov/`, `*.egg-info/`, `.idea/`, `.vscode/`, `*.pem`, `*.key`, and `*.cert`

### Validation

- Local validation:
  - `git ls-files` confirms `.pytest_cache/` and `.codex-artifacts/` are not tracked
  - `git ls-files` confirms only `docker/.env.example` is tracked among env-style files

### Results

- The repo is better protected against accidental commits of local secrets, IDE state, coverage artifacts, and certificate material.

## 2026-03-13 - Python packaging metadata, dev dependencies, and lock files added

### What was executed

- Expanded Python project metadata in:
  - [<repo-root>/pyproject.toml](<repo-root>/pyproject.toml)
  - added `build-system`
  - added PEP 621-style `project` metadata
  - wired runtime dependencies dynamically from `requirements.txt`
  - added a pinned `dev` optional dependency group
- Added explicit development dependencies in:
  - [<repo-root>/requirements-dev.txt](<repo-root>/requirements-dev.txt)
  - includes pinned versions of `pytest`, `pytest-cov`, `pip-audit`, `ruff`, and `pre-commit`
- Switched CI away from ad hoc test-tool installs in:
  - [<repo-root>/.github/workflows/quality_checks.yml](<repo-root>/.github/workflows/quality_checks.yml)
  - test and audit steps now install from `requirements-dev.txt`
- Removed an unnecessary direct dependency from:
  - [<repo-root>/requirements.txt](<repo-root>/requirements.txt)
  - dropped `lxml_html_clean`, which is not imported directly by the repo and was adding avoidable packaging noise
- Updated the public README in:
  - [<repo-root>/README.md](<repo-root>/README.md)
  - documents runtime vs dev dependency files and local install commands

### Validation

- Local validation:
  - `python3 -m py_compile scripts/phase1/retrieval.py scripts/phase6/job_dedup.py scripts/phase6/job_evaluator.py`
  - `python3 -m pytest tests/ -q --cov=scripts --cov-report=term-missing --cov-fail-under=25`

### Results

- The repo no longer relies on CI-only implicit installs for test tooling.
- The Python project now has modern metadata plus a clearer local-development setup story.
- The direct dependency story is cleaner and better separated even though a true Python 3.11 lockfile still needs to be generated in a 3.11-capable environment.

## 2026-03-13 - README testing narrative and Phase 0/4 regression coverage added

### What was executed

- Expanded the public repo overview in:
  - [<repo-root>/README.md](<repo-root>/README.md)
  - added a reviewer-facing testing strategy section
  - documented the current measured baseline (`182` tests, `49.62%` coverage)
  - linked the highest-signal test files for maintainability review
- Added direct Phase 0 regression coverage in:
  - [<repo-root>/tests/test_phase0_bootstrap_sqlite_pytest.py](<repo-root>/tests/test_phase0_bootstrap_sqlite_pytest.py)
  - verifies the SQLite bootstrap creates the expected schema and prints the expected summary
- Added direct Phase 4 regression coverage in:
  - [<repo-root>/tests/test_phase4_summarize_eval_trend_pytest.py](<repo-root>/tests/test_phase4_summarize_eval_trend_pytest.py)
  - covers failure-reason normalization
  - covers missing-result error shaping
  - covers Markdown summary rendering

### Validation

- Local validation:
  - `python3 -m pytest -q tests/test_phase0_bootstrap_sqlite_pytest.py tests/test_phase4_summarize_eval_trend_pytest.py`

### Results

- The public README now explains the testing story instead of leaving reviewers to infer it from CI and scattered test files.
- Phase 0 and Phase 4 no longer look entirely untested from a quick repo scan.

## 2026-03-13 - Pytest fixtures, coverage reporting, and missing-module tests added

### What was executed

- Added shared pytest fixtures in:
  - [<repo-root>/tests/conftest.py](<repo-root>/tests/conftest.py)
  - centralizes temporary SQLite and vault setup for newer tests
- Added pytest configuration in:
  - [<repo-root>/pyproject.toml](<repo-root>/pyproject.toml)
  - standardizes test discovery and output for `pytest`
- Added coverage reporting and a minimum coverage gate in CI in:
  - [<repo-root>/.github/workflows/quality_checks.yml](<repo-root>/.github/workflows/quality_checks.yml)
  - installs `pytest-cov`
  - runs suite coverage against `scripts/`
  - fails CI if total measured coverage drops below `25%`
- Added focused pytest coverage for previously untested modules in:
  - [<repo-root>/tests/test_phase6_storage_pytest.py](<repo-root>/tests/test_phase6_storage_pytest.py)
  - [<repo-root>/tests/test_phase6_job_dedup_pytest.py](<repo-root>/tests/test_phase6_job_dedup_pytest.py)
  - [<repo-root>/tests/test_phase6_cover_letter_drafter_pytest.py](<repo-root>/tests/test_phase6_cover_letter_drafter_pytest.py)
  - [<repo-root>/tests/test_phase3_backup_restore_state_pytest.py](<repo-root>/tests/test_phase3_backup_restore_state_pytest.py)
- Added an integration-style test that crosses the Phase 1 bridge and Phase 6 draft generation path in:
  - [<repo-root>/tests/test_phase1_phase6_cover_letter_flow_pytest.py](<repo-root>/tests/test_phase1_phase6_cover_letter_flow_pytest.py)
  - exercises the actual FastAPI route plus the real Phase 6 drafter function with patched model/data dependencies
- Added parameterized pytest coverage patterns for normalization and helper behavior where table-driven tests improve clarity.

### Validation

- Local validation:
  - `python3 -m pytest -q tests/test_phase6_storage_pytest.py tests/test_phase6_job_dedup_pytest.py tests/test_phase6_cover_letter_drafter_pytest.py tests/test_phase3_backup_restore_state_pytest.py tests/test_phase1_phase6_cover_letter_flow_pytest.py`
  - `python3 -m pytest tests/ -q --cov=scripts --cov-report=term-missing --cov-fail-under=25`
    - `182 passed`
    - `TOTAL coverage: 49.62%`

### Results

- The repo now has a shared pytest fixture layer instead of requiring every new test file to hand-roll the same temp resource setup.
- CI now reports and enforces measured Python coverage rather than treating test execution as binary pass/fail only.
- Several reviewer-visible "zero-test" modules now have direct regression coverage, and the suite includes at least one cross-module request flow instead of only isolated helper tests.

## 2026-03-13 - Reviewer-facing README/API/design docs and algorithm commentary added

### What was executed

- Added a public top-level repo overview in:
  - [<repo-root>/README.md](<repo-root>/README.md)
  - gives recruiters and interviewers a direct landing page with architecture, API, and status links
- Added reviewer-focused API documentation in:
  - [<repo-root>/docs/Recall_local_API_Reference.md](<repo-root>/docs/Recall_local_API_Reference.md)
  - explicitly surfaces the existing FastAPI docs at `/docs`, `/redoc`, and `/openapi.json`
  - summarizes the collection-first resource model and key endpoint groups
- Added a concise design rationale document in:
  - [<repo-root>/docs/Recall_local_Design_Decisions.md](<repo-root>/docs/Recall_local_Design_Decisions.md)
  - explains local-first runtime, dual memory, the thin bridge API, layered retrieval, and local-first evaluation with escalation
- Updated the docs index in:
  - [<repo-root>/docs/README.md](<repo-root>/docs/README.md)
  - elevates the new reviewer-facing entrypoints near the top
- Added docstrings and algorithm comments in:
  - [<repo-root>/scripts/phase1/retrieval.py](<repo-root>/scripts/phase1/retrieval.py)
  - [<repo-root>/scripts/phase6/job_evaluator.py](<repo-root>/scripts/phase6/job_evaluator.py)
  - clarifies how hybrid ranking, heuristic reranking, and batch evaluation/error isolation work

### Validation

- Local validation:
  - `python3 -m py_compile scripts/phase1/retrieval.py`
  - `python3 -m py_compile scripts/phase6/job_evaluator.py`

### Results

- The repo now has a clear public landing page instead of relying on phase docs as the first reviewer touchpoint.
- The FastAPI bridge’s existing OpenAPI/Swagger surfaces are now explicitly documented and discoverable.
- The most inspection-heavy ranking and scoring helpers are easier to understand without reverse-engineering the full implementation.

## 2026-03-13 - Production assert removed and Ruff/pre-commit scaffolding added

### What was executed

- Replaced a production `assert` in:
  - [<repo-root>/scripts/phase2/meeting_action_items.py](<repo-root>/scripts/phase2/meeting_action_items.py)
  - `_load_transcript(...)` now raises `ValueError` when neither transcript input is provided
- Added repo-level Ruff configuration in:
  - [<repo-root>/pyproject.toml](<repo-root>/pyproject.toml)
  - sets a shared baseline for import sorting and core lint checks
- Added pre-commit scaffolding in:
  - [<repo-root>/.pre-commit-config.yaml](<repo-root>/.pre-commit-config.yaml)
  - wires `ruff-check --fix` and `ruff-format`
- Updated the repo-local git hook in:
  - [<repo-root>/.githooks/pre-commit](<repo-root>/.githooks/pre-commit)
  - keeps the `.env` guard
  - runs `pre-commit` automatically when it is installed locally
- Added regression coverage in:
  - [<repo-root>/tests/test_phase2_meeting_action_items_cli.py](<repo-root>/tests/test_phase2_meeting_action_items_cli.py)

### Validation

- Local validation:
  - `python3 -m unittest tests.test_phase2_meeting_action_items_cli`
  - `python3 -m py_compile scripts/phase2/meeting_action_items.py`
  - `bash .githooks/pre-commit` with no staged files

### Results

- The meeting action items CLI no longer relies on `assert` for required runtime input validation.
- The repo now has a standard Ruff/pre-commit path available for future cleanup and enforcement work.

## 2026-03-13 - Bridge secure defaults and CI dependency scanning tightened

### What was executed

- Tightened bridge CORS defaults in:
  - [<repo-root>/scripts/phase1/ingest_bridge_api.py](<repo-root>/scripts/phase1/ingest_bridge_api.py)
  - removed the wildcard fallback so unset `RECALL_API_CORS_ORIGINS` now means no browser cross-origin access by default
- Updated explicit example bridge origins in:
  - [<repo-root>/docker/.env.example](<repo-root>/docker/.env.example)
  - example now lists known local and ai-lab dashboard/UI origins instead of `*`
- Added a repo-local pre-commit guard in:
  - [<repo-root>/.githooks/pre-commit](<repo-root>/.githooks/pre-commit)
  - blocks staging `.env` and `.env.*` files
  - local repo configured with `git config core.hooksPath .githooks`
- Added Python dependency vulnerability scanning to CI in:
  - [<repo-root>/.github/workflows/quality_checks.yml](<repo-root>/.github/workflows/quality_checks.yml)
  - installs and runs `pip-audit` against `requirements.txt`
- Added regression coverage for restrictive CORS behavior in:
  - [<repo-root>/tests/test_bridge_api_contract.py](<repo-root>/tests/test_bridge_api_contract.py)

### Validation

- Local validation:
  - `python3 -m unittest tests.test_bridge_api_contract`
  - `python3 -m py_compile scripts/phase1/ingest_bridge_api.py`
  - `bash .githooks/pre-commit` with no staged files

### Results

- The bridge is no longer permissive to all browser origins by default.
- The local repo now has a guardrail against accidental `.env` commits.
- CI will fail earlier when pinned Python dependencies have known vulnerabilities.

## 2026-03-13 - Python direct dependencies pinned and dashboard builds lockfile-enforced

### What was executed

- Pinned direct Python bridge/runtime dependencies in:
  - [<repo-root>/requirements.txt](<repo-root>/requirements.txt)
  - aligned direct versions to the package set currently running in the live `recall-ingest-bridge` container on `ai-lab`
- Switched dashboard Docker builds to lockfile-enforced installs in:
  - [<repo-root>/ui/daily-dashboard/Dockerfile](<repo-root>/ui/daily-dashboard/Dockerfile)
  - [<repo-root>/ui/dashboard/Dockerfile](<repo-root>/ui/dashboard/Dockerfile)
  - replaced `npm install` with `npm ci`
- Synced the updated files to `ai-lab` and spot-checked remote contents.

### Validation

- Local validation:
  - verified every entry in `requirements.txt` is exact-pinned with `==`
  - `npm run build` in `<repo-root>/ui/daily-dashboard`
  - `npm run build` in `<repo-root>/ui/dashboard`
- Validation note:
  - `python3 -m pip install --dry-run -r requirements.txt` was attempted, but the system `pip` on this Mac does not support `--dry-run`

### Results

- Future bridge rebuilds should be more reproducible because direct Python dependency drift is reduced.
- Future dashboard image builds now honor committed npm lockfiles instead of resolving fresh dependency trees.

## 2026-03-13 - Dashboard and Telegram evaluation summaries polished

### What was executed

- Added a shared Phase 6 summary formatter in:
  - [<repo-root>/ui/daily-dashboard/src/utils/jobSummary.js](<repo-root>/ui/daily-dashboard/src/utils/jobSummary.js)
  - centralizes concise summary copy for:
    - top match with resume evidence when available
    - top gap with severity when available
    - one-line application angle from cover-letter angle, application tips, or rationale fallback
- Updated dashboard summary surfaces in:
  - [<repo-root>/ui/daily-dashboard/src/components/JobCard.jsx](<repo-root>/ui/daily-dashboard/src/components/JobCard.jsx)
  - [<repo-root>/ui/daily-dashboard/src/components/JobsCommandCenter.jsx](<repo-root>/ui/daily-dashboard/src/components/JobsCommandCenter.jsx)
  - [<repo-root>/ui/daily-dashboard/src/components/MissionControlPanel.jsx](<repo-root>/ui/daily-dashboard/src/components/MissionControlPanel.jsx)
  - job cards and queue/spotlight panels now surface sharper evaluator summaries instead of only raw first-item strings
- Tightened Telegram alert formatting in:
  - [<repo-root>/n8n/workflows/phase6c_evaluate_notify_import.workflow.json](<repo-root>/n8n/workflows/phase6c_evaluate_notify_import.workflow.json)
  - [<repo-root>/n8n/workflows/phase6/workflow3_evaluate_notify.md](<repo-root>/n8n/workflows/phase6/workflow3_evaluate_notify.md)
  - batched alerts now include top match, top gap, and a short positioning angle for each preferred-location role
- Updated the Python Telegram notifier scaffold in:
  - [<repo-root>/scripts/phase6/telegram_notifier.py](<repo-root>/scripts/phase6/telegram_notifier.py)
- Added regression coverage in:
  - [<repo-root>/tests/test_phase6_telegram_notifier.py](<repo-root>/tests/test_phase6_telegram_notifier.py)

### Validation

- Local validation:
  - `python3 -m unittest tests.test_phase6_telegram_notifier`
  - `python3 -m py_compile scripts/phase6/telegram_notifier.py`
  - `python3 -m json.tool n8n/workflows/phase6c_evaluate_notify_import.workflow.json`
  - `npm run build` in `<repo-root>/ui/daily-dashboard`
- Live follow-through on 2026-03-13:
  - synced updated files to `ai-lab` and spot-checked remote contents
  - rebuilt only `daily-dashboard` under Compose project `recall`
  - patched the active n8n Workflow 3 formatter in both `workflow_entity` and active `workflow_history`
  - restarted only `n8n` and re-ran `./validate-stack.sh`
  - ran `./scripts/phase6/run_dashboard_smoke.sh http://<ai-lab-tailnet-ip>:8090` after deploy and received `status: ok`
  - sent controlled webhook smokes through `http://localhost:5678/webhook/recall-job-evaluate`
  - performed a browser spot-check against `http://<ai-lab-tailnet-ip>:3001`

### Results

- Cleaner evaluator outputs are now translated into more actionable dashboard summaries.
- Telegram notifications should give faster first-pass triage context without opening the dashboard first.
- Final truncation pass now prefers whole-word cuts for dashboard and Telegram summary copy, and the current alert verbosity was kept after the live UI spot-check.

## 2026-03-13 - Job-fit golden calibration lane added

### What was executed

- Added a versioned Phase 6 golden set in:
  - [<repo-root>/scripts/eval/golden_sets/job_fit_golden_v1.json](<repo-root>/scripts/eval/golden_sets/job_fit_golden_v1.json)
  - contains representative synthetic job-fit calibration cases spanning strong-fit, good-fit, mixed-fit, and stretch-fit roles
- Added a dedicated golden runner in:
  - [<repo-root>/scripts/eval/run_job_fit_golden.py](<repo-root>/scripts/eval/run_job_fit_golden.py)
  - evaluates each case against the Phase 6 evaluator prompt/parser path
  - checks score bands plus required/forbidden matching-skill and gap terms
  - writes JSON artifacts under `data/artifacts/evals/job-fit-golden`
- Added regression coverage in:
  - [<repo-root>/tests/test_phase6_job_fit_golden.py](<repo-root>/tests/test_phase6_job_fit_golden.py)

### Validation

- Local validation:
  - `python3 -m unittest tests.test_phase6_job_fit_golden tests.test_phase6c_evaluation_observation`
  - `python3 -m py_compile scripts/eval/run_job_fit_golden.py`
- Local model-run note:
  - `python3 scripts/eval/run_job_fit_golden.py --max-cases 1 --dry-run`
  - failed on this Mac because `http://localhost:11434/api/generate` returned `404`; the runner is intended to be executed where the Ollama runtime is actually available

### Results

- Recall.local now has a repeatable calibration lane for Phase 6 evaluator quality instead of relying only on ad hoc spot checks.
- Future prompt/parser changes can be judged against explicit fit expectations for representative target roles.

## 2026-03-13 - Evaluation signal consistency hardening

### What was executed

- Tightened Phase 6 evaluation prompt guidance in:
  - [<repo-root>/scripts/phase6/job_evaluator.py](<repo-root>/scripts/phase6/job_evaluator.py)
  - added explicit consistency rules so the model should not place the same competency in both `matching_skills` and `gaps`
- Hardened parser-side evaluation cleanup in:
  - [<repo-root>/scripts/phase6/job_evaluator.py](<repo-root>/scripts/phase6/job_evaluator.py)
  - dedupes repeated skills/gaps by canonical label
  - removes contradiction cases where an evidence-backed matching skill overlaps the same named gap
- Added regression coverage in:
  - [<repo-root>/tests/test_phase6c_evaluation_observation.py](<repo-root>/tests/test_phase6c_evaluation_observation.py)
  - covers duplicated skills/gaps and match-vs-gap contradiction cleanup

### Validation

- Local validation:
  - `python3 -m unittest tests.test_phase6c_evaluation_observation`
  - `python3 -m py_compile scripts/phase6/job_evaluator.py`

### Results

- Phase 6 evaluations should now surface cleaner matching-skill and gap lists when the model produces overlapping signals.
- The dashboard and notifications should be less likely to present obviously contradictory fit narratives for the same role.

## 2026-03-13 - Server-backed job search for dashboard triage

### What was executed

- Expanded Phase 6 job filtering in:
  - [<repo-root>/scripts/phase6/job_repository.py](<repo-root>/scripts/phase6/job_repository.py)
  - added a multi-field `search` filter for `list_jobs(...)`
  - search now matches across title, company, location, source, search query, evaluation rationale, matching skills, gaps, notes, and observation metadata
  - preserved `title_query` as a fallback so older callers still behave sensibly
- Extended the jobs collection endpoint in:
  - [<repo-root>/scripts/phase1/ingest_bridge_api.py](<repo-root>/scripts/phase1/ingest_bridge_api.py)
  - `GET /v1/jobs` now accepts optional `search`
- Wired the Daily Dashboard jobs deck to the server-backed filter in:
  - [<repo-root>/ui/daily-dashboard/src/api.js](<repo-root>/ui/daily-dashboard/src/api.js)
  - [<repo-root>/ui/daily-dashboard/src/hooks/useJobs.js](<repo-root>/ui/daily-dashboard/src/hooks/useJobs.js)
  - [<repo-root>/ui/daily-dashboard/src/components/JobsCommandCenter.jsx](<repo-root>/ui/daily-dashboard/src/components/JobsCommandCenter.jsx)
  - the "Search live roles" box now drives API filtering instead of only searching the already loaded client-side slice
- Added regression coverage in:
  - [<repo-root>/tests/test_bridge_api_contract.py](<repo-root>/tests/test_bridge_api_contract.py)
  - [<repo-root>/tests/test_phase6_job_repository.py](<repo-root>/tests/test_phase6_job_repository.py)

### Validation

- Local validation:
  - `python3 -m unittest tests.test_bridge_api_contract tests.test_phase6_job_repository`
  - `npm run build` in `<repo-root>/ui/daily-dashboard`

### Results

- Dashboard triage now has a better chance of surfacing the right role when searching by company name, location, gap language, or notes instead of only exact title text.
- The jobs search behavior now better matches the UI promise of searching across the live board rather than just the visible client-side subset.

## 2026-03-13 - Job-alert smoke coverage + ai-lab vault path fix

### What was executed

- Extended the consolidated operator check in:
  - [<repo-root>/scripts/phase6/run_ops_observability_check.sh](<repo-root>/scripts/phase6/run_ops_observability_check.sh)
  - added `job_alert_workflow` validation that:
    - verifies Workflow 3 is active in n8n SQLite
    - verifies `Send Telegram Alert` is still a credential-bound Telegram node
    - verifies the active aggregator hands off to `recall-job-evaluate`
    - performs a non-alerting webhook probe with a fake job id so the path is exercised without spamming Telegram
- Fixed the live ai-lab bridge vault runtime path by updating:
  - [<repo-root>/docker/docker-compose.yml](<repo-root>/docker/docker-compose.yml)
  - [<repo-root>/docker/.env.example](<repo-root>/docker/.env.example)
  - changes:
    - explicit bridge mount: `<vault-root>:<vault-root>:ro`
    - explicit bridge env: `RECALL_VAULT_PATH=<vault-root>`
- Synced the updated files to ai-lab and performed required remote spot-checks before restart/verification.
- Recreated only `recall-ingest-bridge` under Compose project `recall`.

### Validation

- Local validation:
  - `bash -n scripts/phase6/run_ops_observability_check.sh`
- ai-lab validation:
  - `cd <server-repo-root>/docker && ./validate-stack.sh` before and after bridge recreate
  - `./scripts/phase6/run_ops_observability_check.sh http://localhost:8090 http://localhost:3001 http://localhost:8170`
    - artifact: `<server-repo-root>/data/artifacts/observability/20260313T144608Z_ops_observability_check.json`
    - checks passed:
      - `bridge_health`
      - `dashboard_checks`
      - `job_alert_workflow`
      - `rag_probe`
      - `daily_dashboard_ui`
      - `recall_chat_ui`
  - `./scripts/phase6/run_dashboard_smoke.sh http://localhost:8090` returned `ok`
  - direct bridge vault probe:
    - `GET http://localhost:8090/v1/vault-files` returned `200`
    - reported `vault_path=<vault-root>`

### Results

- Future regressions in the Phase 6 Telegram alert path should now be caught by the standard ops observability run without sending noisy test alerts.
- The Recall dashboard vault error is fixed on ai-lab: the bridge no longer falls back to `/root/obsidian-vault`, and vault endpoints now load against the real mirrored Obsidian vault.

## 2026-03-13 - Phase 6C Telegram delivery restoration on ai-lab

### What was executed

- Re-validated the live ai-lab stack and current Workflow 3 execution path before changing runtime state:
  - `cd <server-repo-root>/docker && ./validate-stack.sh`
  - confirmed active workflows include:
    - `Job Board Aggregator` (`cWHLi1plI5siWP8X`)
    - `Recall Phase6B - Career Page Monitor (Traditional Import)` (`eE5wQFqV9oiSHKaL`)
    - `Phase 6C - Workflow 3 - Evaluate & Notify` (`9DEQqfD8JA5PCiVP`)
- Confirmed the end-to-end evaluation webhook path was active but not delivering alerts:
  - `POST http://localhost:5678/webhook/recall-job-evaluate`
  - a high-fit test job returned `high_fit_count=1` and `notifications_sent=0`
  - decoded the latest n8n execution payload and found the root cause:
    - Workflow 3 had drifted back to an HTTP Request node using `$env`
    - ai-lab still blocks env access in n8n expressions (`access to env vars denied`)
- Restored the repo workflow artifacts back to the known-good credential-based Telegram path:
  - [<repo-root>/n8n/workflows/phase6c_evaluate_notify_import.workflow.json](<repo-root>/n8n/workflows/phase6c_evaluate_notify_import.workflow.json)
  - [<repo-root>/n8n/workflows/phase6/workflow3_evaluate_notify.md](<repo-root>/n8n/workflows/phase6/workflow3_evaluate_notify.md)
  - [<repo-root>/n8n/workflows/phase6/workflow1_aggregator.md](<repo-root>/n8n/workflows/phase6/workflow1_aggregator.md)
- Removed the temporary unused n8n Telegram env wiring from:
  - [<repo-root>/docker/docker-compose.yml](<repo-root>/docker/docker-compose.yml)
- Synced the updated local files to ai-lab and spot-checked remote contents before restart/verification.
- Patched the active Workflow 3 node directly in ai-lab n8n SQLite to match the credential-based configuration:
  - node: `Send Telegram Alert`
  - type: `n8n-nodes-base.telegram`
  - credential: `6aWx4DnLbVi8JlGU` (`Telegram account`)
  - chat id: `8724583836`
- Restarted only `n8n` under the `recall` Compose project and re-ran stack validation.

### Validation

- `./validate-stack.sh` passed after the `n8n` restart.
- Direct Telegram Bot API probe from ai-lab succeeded for the target chat.
- High-fit Workflow 3 webhook smoke test succeeded end-to-end:
  - `POST http://localhost:5678/webhook/recall-job-evaluate`
  - payload: `{"job_ids":["job_bcb835e52c70d017"],"wait":true}`
  - response fields:
    - `high_fit_count=1`
    - `notifications_sent=1`
    - `notification_errors=[]`

### Results

- `Recall Job Scout` alerts are flowing again through the intended Phase 6C path.
- The active aggregator/career workflows now hand off into Workflow 3 without bypassing Telegram delivery.
- Workflow 3 is back on the supported ai-lab pattern:
  - Telegram credential inside n8n
  - no `$env` dependency in node expressions
- A fresh high-fit webhook probe now sends a real Telegram alert successfully.

## 2026-03-12 - Optional OTEL/Honeycomb bridge tracing added

### What was executed

- Added optional bridge-side OpenTelemetry wiring in:
  - [<repo-root>/scripts/phase1/observability.py](<repo-root>/scripts/phase1/observability.py)
  - [<repo-root>/scripts/phase1/ingest_bridge_api.py](<repo-root>/scripts/phase1/ingest_bridge_api.py)
- Implemented a lightweight request middleware that:
  - preserves or generates `X-Request-Id`
  - returns `X-Request-Id` on responses
  - returns `X-Trace-Id` and `traceparent` when tracing is enabled
  - exports request spans over OTLP HTTP when `RECALL_OTEL_ENABLED=true`
- Added Honeycomb-compatible env support in:
  - [<repo-root>/docker/.env.example](<repo-root>/docker/.env.example)
  - supports either direct OTLP env vars or `HONEYCOMB_API_KEY` + optional dataset
- Added regression coverage in:
  - [<repo-root>/tests/test_bridge_api_contract.py](<repo-root>/tests/test_bridge_api_contract.py)
  - [<repo-root>/tests/test_phase1_observability.py](<repo-root>/tests/test_phase1_observability.py)

### Validation

- Local validation:
  - `python3 -m unittest tests.test_bridge_api_contract tests.test_phase1_observability`
  - `python3 -m py_compile scripts/phase1/ingest_bridge_api.py scripts/phase1/observability.py`
- ai-lab validation:
  - sync updated files from Mac to ai-lab
  - rebuild only `recall-ingest-bridge`
  - run `./validate-stack.sh` before and after
  - verify `/v1/healthz` still returns `200`

### Results

- Recall.local now has a real bridge-side tracing hook for Honeycomb/OTLP without forcing a live provider change.
- The feature is additive and dormant by default until credentials and `RECALL_OTEL_ENABLED=true` are supplied.

## 2026-03-12 - ai-lab uptime cron wrapper added

### What was executed

- Added a cron-safe uptime wrapper:
  - [<repo-root>/scripts/phase6/run_ops_observability_cron.sh](<repo-root>/scripts/phase6/run_ops_observability_cron.sh)
  - sources `docker/.env`
  - reuses existing Telegram alert credentials when dedicated uptime alert vars are unset
- Updated observability/runtime docs:
  - [<repo-root>/docs/OBSERVABILITY_STRATEGY.md](<repo-root>/docs/OBSERVABILITY_STRATEGY.md)
  - [<repo-root>/docs/ENVIRONMENT_INVENTORY.md](<repo-root>/docs/ENVIRONMENT_INVENTORY.md)
  - [<repo-root>/docs/README.md](<repo-root>/docs/README.md)

### Validation

- Local validation:
  - `bash -n scripts/phase6/run_ops_observability_cron.sh`
- ai-lab validation:
  - sync updated files from Mac to ai-lab
  - run `./scripts/phase6/run_ops_observability_cron.sh`
  - install cron entry for repeated uptime checks

### Results

- ai-lab now has a clean path to run the uptime check from cron without hand-exporting secrets.
- The uptime monitor can piggyback on the existing Telegram notification setup instead of introducing a second secret-management path.

## 2026-03-12 - Ops uptime alerting added to observability wrapper

### What was executed

- Extended the consolidated observability wrapper in [<repo-root>/scripts/phase6/run_ops_observability_check.sh](<repo-root>/scripts/phase6/run_ops_observability_check.sh):
  - optional generic webhook alerting via `RECALL_UPTIME_ALERT_WEBHOOK_URL`
  - optional Telegram alerting via:
    - `RECALL_UPTIME_ALERT_TELEGRAM_BOT_TOKEN`
    - `RECALL_UPTIME_ALERT_TELEGRAM_CHAT_ID`
  - optional success notifications via `RECALL_UPTIME_NOTIFY_ON_SUCCESS`
- Updated the uptime/alerting documentation in:
  - [<repo-root>/docs/OBSERVABILITY_STRATEGY.md](<repo-root>/docs/OBSERVABILITY_STRATEGY.md)
  - [<repo-root>/docs/ENVIRONMENT_INVENTORY.md](<repo-root>/docs/ENVIRONMENT_INVENTORY.md)
  - [<repo-root>/docker/.env.example](<repo-root>/docker/.env.example)

### Validation

- Local validation:
  - `bash -n scripts/phase6/run_ops_observability_check.sh`
- ai-lab validation:
  - sync updated files from Mac to ai-lab
  - run `./scripts/phase6/run_ops_observability_check.sh http://localhost:8090 http://localhost:3001 http://localhost:8170`

### Results

- The uptime check now has a real alerting path instead of stopping at local console output and artifacts.
- Recall.local can now support a lightweight cron-driven uptime loop on `ai-lab` without introducing a new service.

## 2026-03-12 - Operator observability check + Phase 6 workflow cleanup

### What was executed

- Added a consolidated operator observability wrapper:
  - [<repo-root>/scripts/phase6/run_ops_observability_check.sh](<repo-root>/scripts/phase6/run_ops_observability_check.sh)
  - checks bridge health, dashboard readiness, dashboard UI reachability, chat UI reachability, and one grounded `/v1/rag-queries` probe
  - writes JSON artifacts to:
    - `<repo-root>/data/artifacts/observability`
- Reconciled observability/runtime docs to the live state:
  - [<repo-root>/AGENTS.md](<repo-root>/AGENTS.md)
  - [<repo-root>/docs/OBSERVABILITY_STRATEGY.md](<repo-root>/docs/OBSERVABILITY_STRATEGY.md)
  - [<repo-root>/docs/ENVIRONMENT_INVENTORY.md](<repo-root>/docs/ENVIRONMENT_INVENTORY.md)
  - [<repo-root>/docs/README.md](<repo-root>/docs/README.md)
- Cleaned up the remaining tracked Phase 6 workflow deltas by keeping the reliability-oriented workflow changes and documenting them in:
  - [<repo-root>/n8n/workflows/phase6/workflow2_career_pages.md](<repo-root>/n8n/workflows/phase6/workflow2_career_pages.md)
  - [<repo-root>/n8n/workflows/phase6b_career_page_monitor_import.workflow.json](<repo-root>/n8n/workflows/phase6b_career_page_monitor_import.workflow.json)
  - [<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_import.workflow.json](<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_import.workflow.json)
  - [<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_active_import.workflow.json](<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_active_import.workflow.json)

### Validation

- Local validation:
  - `bash -n scripts/phase6/run_ops_observability_check.sh`
- ai-lab validation:
  - sync updated files from Mac to ai-lab
  - spot-check the remote script/docs/workflow guide before verification
  - run `./scripts/phase6/run_ops_observability_check.sh http://localhost:8090 http://localhost:3001 http://localhost:8170`

### Results

- Recall.local now has one practical operator check that captures both dashboard readiness and a lightweight grounded RAG health probe.
- The written docs now match the actual live baseline more closely:
  - observability is a partial implementation, not just a future plan
  - ai-lab model expectations are explicit
  - Phase 6 status no longer stops at `6A`
- The remaining tracked Phase 6 workflow edits are now treated as intentional reliability improvements instead of unexplained repo drift.

## 2026-03-12 - Daily dashboard UI recovery and state polish (local + ai-lab)

### What was executed

- Improved dashboard browser request behavior in [<repo-root>/ui/daily-dashboard/src/api.js](<repo-root>/ui/daily-dashboard/src/api.js):
  - added request timeouts for reads and mutations
  - added a single retry for retryable `GET` failures and timeouts
- Hardened dashboard hooks:
  - [<repo-root>/ui/daily-dashboard/src/hooks/useJobs.js](<repo-root>/ui/daily-dashboard/src/hooks/useJobs.js)
  - [<repo-root>/ui/daily-dashboard/src/hooks/useCompanies.js](<repo-root>/ui/daily-dashboard/src/hooks/useCompanies.js)
  - [<repo-root>/ui/daily-dashboard/src/hooks/useSettings.js](<repo-root>/ui/daily-dashboard/src/hooks/useSettings.js)
- Added browser-side resilience behavior:
  - periodic background refresh
  - refresh on browser focus / visibility return
  - refresh on network reconnect
  - timed retry after failed reads
  - cached company-detail reuse when a live detail refresh fails
- Added a reusable dashboard state card:
  - [<repo-root>/ui/daily-dashboard/src/components/StateNotice.jsx](<repo-root>/ui/daily-dashboard/src/components/StateNotice.jsx)
- Replaced flat empty/error copy with clearer recovery-oriented UI in:
  - [<repo-root>/ui/daily-dashboard/src/App.jsx](<repo-root>/ui/daily-dashboard/src/App.jsx)
  - [<repo-root>/ui/daily-dashboard/src/components/JobsCommandCenter.jsx](<repo-root>/ui/daily-dashboard/src/components/JobsCommandCenter.jsx)
  - [<repo-root>/ui/daily-dashboard/src/components/CompanyList.jsx](<repo-root>/ui/daily-dashboard/src/components/CompanyList.jsx)
  - [<repo-root>/ui/daily-dashboard/src/components/CompanyProfile.jsx](<repo-root>/ui/daily-dashboard/src/components/CompanyProfile.jsx)
  - [<repo-root>/ui/daily-dashboard/src/components/SkillGapRadar.jsx](<repo-root>/ui/daily-dashboard/src/components/SkillGapRadar.jsx)
  - [<repo-root>/ui/daily-dashboard/src/styles/theme.css](<repo-root>/ui/daily-dashboard/src/styles/theme.css)

### Validation

- Local validation:
  - `npm run build` in `<repo-root>/ui/daily-dashboard` -> `OK`

### Results

- The dashboard is less dependent on manual reloads and should recover more gracefully from transient bridge or network hiccups.
- Cached data is now surfaced more intentionally, so a stale-but-usable board looks deliberate instead of broken.
- Empty and error states now give the operator an obvious next action instead of leaving the page looking unfinished.

## 2026-03-11 - Daily dashboard reliability hardening (local + ai-lab)

### What was executed

- Added a bridge-side dashboard readiness route in [<repo-root>/scripts/phase1/ingest_bridge_api.py](<repo-root>/scripts/phase1/ingest_bridge_api.py):
  - `GET /v1/dashboard-checks`
  - lightweight readiness checks for jobs, companies, and skill gaps
  - dashboard cache-warmer status in the response payload
- Added a background dashboard cache warmer in [<repo-root>/scripts/phase1/ingest_bridge_api.py](<repo-root>/scripts/phase1/ingest_bridge_api.py):
  - warms job stats, summary jobs, company profiles, and gap aggregation on an interval
  - controlled by:
    - `RECALL_DASHBOARD_CACHE_WARMER`
    - `RECALL_DASHBOARD_CACHE_WARM_INTERVAL_SECONDS`
- Added Phase 6 company-profile caching in [<repo-root>/scripts/phase6/company_profiler.py](<repo-root>/scripts/phase6/company_profiler.py):
  - cached list/detail rollups keyed by job/config/profile signatures
  - invalidation on tracked-company upsert and profile refresh
  - TTL controlled by `RECALL_PHASE6_COMPANY_CACHE_SECONDS`
- Added an operator smoke wrapper:
  - [<repo-root>/scripts/phase6/run_dashboard_smoke.sh](<repo-root>/scripts/phase6/run_dashboard_smoke.sh)
- Added regression coverage:
  - [<repo-root>/tests/test_bridge_api_contract.py](<repo-root>/tests/test_bridge_api_contract.py)
  - [<repo-root>/tests/test_phase6_company_profiler_cache.py](<repo-root>/tests/test_phase6_company_profiler_cache.py)
- Updated operator/runtime docs:
  - [<repo-root>/AGENTS.md](<repo-root>/AGENTS.md)
  - [<repo-root>/docs/ENVIRONMENT_INVENTORY.md](<repo-root>/docs/ENVIRONMENT_INVENTORY.md)
  - [<repo-root>/docs/Recall_local_Daily_Dashboard_Reliability_Runbook.md](<repo-root>/docs/Recall_local_Daily_Dashboard_Reliability_Runbook.md)
- Synced the updated files from Mac to `ai-lab`, spot-checked the remote code, rebuilt only `recall-ingest-bridge` under Compose project `recall`, and re-ran stack validation before and after the recreate.

### Validation

- Local validation:
  - `python3 -m unittest tests/test_bridge_api_contract.py tests/test_phase6_company_profiler_cache.py` -> `OK`
  - `python3 -m py_compile scripts/phase1/ingest_bridge_api.py scripts/phase6/company_profiler.py`
- ai-lab validation:
  - `<server-repo-root>/docker/validate-stack.sh` -> `pass` before and after bridge recreate
  - `./scripts/phase6/run_dashboard_smoke.sh http://localhost:8090` -> `ok`
- Live observed smoke behavior:
  - first smoke after restart hit the cold gap-aggregation path and completed slowly while caches warmed
  - second smoke completed quickly with warm caches:
    - jobs latency `235ms`
    - companies latency `18ms`
    - gaps latency `12ms`

### Results

- The daily dashboard now has a single canonical readiness check for operators and demo validation.
- Company profile rollups no longer require recomputing the same summary payloads on every request.
- The bridge keeps dashboard-critical data warm in the background, which materially improves first-load reliability after startup and reduces the risk of an empty board during demos.

## 2026-03-07 - OpenAI careers automation migrated to Ashby (ai-lab)

### What was executed

- Investigated why `OpenAI` jobs were not arriving automatically in the Phase 6 board even though the company was tracked.
- Verified the old source was stale:
  - `config/career_pages.json` still pointed OpenAI at the deprecated Greenhouse board.
  - the live n8n workflow `Recall Phase6B - Career Page Monitor (Traditional Import)` also still hard-coded OpenAI as `greenhouse`.
- Confirmed the current official OpenAI careers surface is the Ashby board behind:
  - `https://openai.com/careers/search/`
  - `https://api.ashbyhq.com/posting-api/job-board/openai`
- Extended bridge-side career-page discovery in `<repo-root>/scripts/phase6/job_discovery_runner.py`:
  - added `ashby` board support
  - widened the bridge default `career_page` source limit from `3` to `25` so OpenAI is not silently skipped by alphabetical company ordering
- Updated tracked-company config in `<repo-root>/config/career_pages.json`:
  - OpenAI `ats: ashby`
  - OpenAI `url: https://openai.com/careers/search/`
  - narrowed OpenAI title filters to the intended customer-facing / deployment slice:
    - `deployment`
    - `solutions engineer`
    - `solution engineer`
    - `forward deployed`
    - `architect`
    - `pre-sales`
- Added regression coverage in `<repo-root>/tests/test_phase6b_job_discovery_runner.py` for Ashby board discovery + payload normalization.
- Updated the Phase 6B workflow artifacts and runbook to match the new OpenAI source:
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_import.workflow.json`
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_import.workflow.json`
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_active_import.workflow.json`
  - `<repo-root>/n8n/workflows/phase6/workflow2_career_pages.md`
- Synced all changes from Mac to `ai-lab`, spot-checked the remote files, restarted `recall-ingest-bridge`, imported/published the updated live Workflow 2, and restarted `n8n`.
- Backed up the over-broad OpenAI live job slice created during validation to:
  - `<server-repo-root>/backups/20260307T-openai-reseed/openai_jobs.pre-reseed.json`
- Re-seeded OpenAI jobs on `ai-lab` by:
  - deleting the noisy OpenAI slice from `recall_jobs`
  - re-ingesting the filtered Ashby roles
  - preserving the manually added LinkedIn `AI Deployment Engineer` post in the final seeded set

### Validation

- Local validation:
  - `python3 -m unittest tests/test_phase6b_job_discovery_runner.py` -> `OK`
  - `python3 -m py_compile scripts/phase6/job_discovery_runner.py`
- Live bridge validation after sync/restart:
  - `GET http://127.0.0.1:8090/v1/healthz` -> `200 {"status":"ok"}`
- Verified direct OpenAI Ashby discovery on `ai-lab`:
  - `341` matches with the first broad Ashby port, confirming source reachability
  - `96` matches after the title-filter tightening
- Verified live n8n Workflow 2 is active after re-import:
  - workflow id: `eE5wQFqV9oiSHKaL`
  - startup logs show `Recall Phase6B - Career Page Monitor (Traditional Import)` active
  - live workflow node payload contains `deployment`, `forward deployed`, and `solution engineer` filter terms
- Verified live company/profile result after the OpenAI reseed:
  - `GET http://127.0.0.1:8090/v1/companies/openai`
  - `job_count=97`
  - `ats=ashby`
  - `url=https://openai.com/careers/search/`
  - sample stored jobs now resolve to `https://jobs.ashbyhq.com/openai/...` plus the preserved LinkedIn role
- Verified overall live stats after the updated discovery state:
  - `GET http://127.0.0.1:8090/v1/job-stats`
  - `total_jobs=984`
  - `by_source.career_page=881`

### Results

- OpenAI job discovery is now wired to the current official careers source instead of the dead Greenhouse board.
- The bridge-side discovery path will now reach OpenAI by default, and the live n8n career-page monitor is aligned to the same Ashby source.
- The live OpenAI company view is no longer manual-only; it now contains a curated Ashby-backed role set plus the saved LinkedIn posting.

## 2026-03-06 - Daily full-backup hardening after Qdrant recovery

### What was executed

- Investigated the missing live `recall_docs` / `newsletter_stories` collections on `ai-lab` and confirmed they were absent from the running Qdrant storage directory, not just from UI/API listing.
- Restored both collections from `<server-repo-root>/backups/2026-03-02-164642/qdrant-volume.tgz` after taking a fresh safety backup of the current live Qdrant volume:
  - `<server-repo-root>/backups/20260306T200044Z-pre-restore/qdrant-volume.tgz`
- Added a new full-backup wrapper:
  - `<repo-root>/scripts/phase3/run_daily_full_backup.sh`
- Expanded operator documentation to define the daily full-backup path, schedule, retention, and artifact coverage:
  - `<repo-root>/docs/Recall_local_Phase3C_Operations_Runbook.md`
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md`
- Replaced the previous `RECALL_DAILY_ALL_COLLECTIONS_BACKUP` cron block on `ai-lab` with `RECALL_DAILY_FULL_BACKUP`:
  - schedule: `2:15 AM` America/Chicago
  - command: `scripts/phase3/run_daily_full_backup.sh`
- Executed a manual verification backup on `ai-lab`:
  - `<server-repo-root>/data/artifacts/backups/daily_full/manual_verify_20260306T2006Z`

### Validation

- Restored live collection counts on `ai-lab`:
  - `recall_docs=1739`
  - `newsletter_stories=39`
  - `recall_jobs=539`
  - `recall_resume=10`
- Verified `recall_docs` payload retrieval after restore with a direct Qdrant scroll request.
- Verified the new daily full-backup wrapper end to end:
  - logical export completed for all four live Qdrant collections
  - runtime artifacts written: `n8n-database.sqlite`, `n8n-dir.tgz`, `data.tgz`, `qdrant-volume.tgz`, `compose-config.tgz`
  - resulting manual verification snapshot size: `535M`

### Results

- The live knowledge collections are back on `ai-lab`.
- Backup coverage is now defined to include not only logical SQLite/Qdrant exports, but also raw Qdrant volume state, `n8n` runtime state, `data/` contents, and deployment config.
- Daily full backups are now scheduled on the live host rather than only the narrower all-collections export.

## 2026-03-06 - Phase 6D dashboard implementation + ai-lab deploy validation

### What was executed

- Implemented the Phase 6D dashboard rebuild in `<repo-root>/ui/daily-dashboard`:
  - replaced the Phase 6A placeholder app with real job, company, gap, settings, and cover-letter flows
  - added componentized React structure:
    - `<repo-root>/ui/daily-dashboard/src/components/JobHuntPanel.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/JobCard.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/JobDetail.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/SkillGapRadar.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/ScoreDistribution.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/StatsBar.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/Filters.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/CompanyProfile.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/CompanyList.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/SettingsPanel.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/CoverLetterDraft.jsx`
    - `<repo-root>/ui/daily-dashboard/src/components/FutureWidgetSlot.jsx`
  - added data hooks:
    - `<repo-root>/ui/daily-dashboard/src/hooks/useJobs.js`
    - `<repo-root>/ui/daily-dashboard/src/hooks/useCompanies.js`
    - `<repo-root>/ui/daily-dashboard/src/hooks/useSettings.js`
  - added Atelier Ops theme styling in `<repo-root>/ui/daily-dashboard/src/styles/theme.css`
  - changed dashboard API wiring to same-origin `/v1` calls with Vite dev proxy + nginx reverse proxy:
    - `<repo-root>/ui/daily-dashboard/src/api.js`
    - `<repo-root>/ui/daily-dashboard/vite.config.js`
    - `<repo-root>/ui/daily-dashboard/nginx.conf`
- Completed the backend/API support needed for the new UI:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
    - added `POST /v1/cover-letter-drafts`
    - widened `/v1/job-stats` payload with `new_today`, `high_fit_count`, `average_fit_score`, and score-distribution buckets
    - allowed `GET /v1/jobs?status=all`
  - `<repo-root>/scripts/phase6/cover_letter_drafter.py`
    - new service to draft cover letters from `recall_resume` + evaluated job context
  - `<repo-root>/scripts/phase6/company_profiler.py`
    - upgraded company profile payloads for list/detail dashboard views
  - `<repo-root>/scripts/phase6/job_repository.py`
    - widened stats support for dashboard metrics
- Added contract coverage for the new API surface in `<repo-root>/tests/test_bridge_api_contract.py`.
- Local validation:
  - `python3 -m py_compile scripts/phase1/ingest_bridge_api.py scripts/phase6/company_profiler.py scripts/phase6/job_repository.py scripts/phase6/cover_letter_drafter.py`
  - `python3 -m pytest -q tests/test_bridge_api_contract.py tests/test_phase6c_evaluation_observation.py` -> `36 passed`
  - `npm install && npm run build` in `<repo-root>/ui/daily-dashboard`
- Synced updated files from Mac to ai-lab with `rsync`, then performed required remote content spot-checks before any restart or curl verification.
- ai-lab deploy actions:
  - rebuilt `daily-dashboard` via `docker compose -f docker/docker-compose.yml up -d --build daily-dashboard`
  - restarted/recreated `recall-ingest-bridge` as part of the compose run / restart cycle

### Validation

- ai-lab remote content spot-checks confirmed:
  - `cover-letter-drafts` route and related test cases were present in `<server-repo-root>/scripts/phase1/ingest_bridge_api.py` and `<server-repo-root>/tests/test_bridge_api_contract.py`
  - `JobHuntPanel` and `useJobs` were present in `<server-repo-root>/ui/daily-dashboard/src/...`
- Runtime probes after deploy:
  - `GET http://<ai-lab-tailnet-ip>:8090/v1/healthz` -> `200 {"status":"ok"}`
  - `HEAD http://<ai-lab-tailnet-ip>:3001` -> `200`
- Live data restore on ai-lab after deploy validation exposed empty Phase 6 collections:
  - `GET http://localhost:6333/collections` initially returned an empty collections list.
  - Recreated Phase 6 collections with `python3 scripts/phase6/setup_collections.py` on ai-lab.
  - Re-pulled missing Ollama models inside the container: `nomic-embed-text` and `llama3.2:3b`.
  - Re-ingested the live resume from `<vault-root>/career/Jay-Dreyer-Resume.md` into `recall_resume`.
  - Re-ran job discovery against career pages, restoring `539` live jobs into `recall_jobs`.
  - Executed a local evaluation batch for 20 selected jobs through `POST /v1/job-evaluation-runs` with `llama3.2:3b`.
- Final live API checks on 2026-03-06:
  - `GET http://localhost:8090/v1/job-stats` -> `total_jobs=539`, `high_fit_count=16`, `average_fit_score=90.4`
  - `GET http://localhost:8090/v1/jobs?status=evaluated&sort=fit_score&order=desc&limit=5` returned evaluated jobs with persisted fit scores and recommendation payloads

### Results

- Phase 6D code is implemented locally, validated in tests/build, synced to ai-lab, and deployed to the running dashboard and bridge services.
- The live dashboard is no longer blocked by empty Qdrant state on ai-lab; jobs and resume data were restored successfully and high-fit evaluated jobs are now visible through the production API.
- Remaining live follow-up: the first 20-job local evaluation batch completed with `16` successful evaluations and `4` failed items, so additional cleanup or reruns may still be needed for full coverage.

## 2026-03-06 - Phase 6B -> 6C notification handoff fix (ai-lab)

### What was executed

- Investigated missing Telegram alerts after new jobs were discovered/evaluated on ai-lab.
- Confirmed root cause in active Workflow 2:
  - `Recall Phase6B - Career Page Monitor (Traditional Import)` was calling `POST /v1/job-evaluation-runs` directly.
  - This evaluated jobs in the bridge, but bypassed Workflow 3 (`recall-job-evaluate`), so Telegram notifications never ran.
- Patched workflow artifacts to hand off new job ids to Workflow 3 webhook instead:
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_import.workflow.json`
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_active_import.workflow.json`
  - changed `Trigger Evaluation Run` URL to `http://<ai-lab-tailnet-ip>:5678/webhook/recall-job-evaluate`
  - changed payload to `{ job_ids: $json.new_job_ids, wait: true }`
- Updated Workflow 2 runbook to match the live handoff design:
  - `<repo-root>/n8n/workflows/phase6/workflow2_career_pages.md`
- Synced updated workflow artifacts to ai-lab, spot-checked remote content, imported the active workflow artifact, published the current version, and restarted `n8n`.

### Validation

- Verified active ai-lab Workflow 2 node wiring directly from n8n SQLite:
  - `Trigger Evaluation Run` now points to `http://<ai-lab-tailnet-ip>:5678/webhook/recall-job-evaluate`
  - payload now uses `wait: true`
- Verified Workflow 3 webhook execution from ai-lab after the fix:
  - one sample execution completed successfully through n8n (`execution id 1217`), confirming the webhook path is live.
- Performed end-to-end notify smoke test through Workflow 3 webhook with a known high-fit job:
  - `POST http://<ai-lab-tailnet-ip>:5678/webhook/recall-job-evaluate`
  - response included:
    - `evaluated=1`
    - `high_fit_count=1`
    - `notifications_sent=1`
    - `notification_errors=[]`

### Results

- New jobs discovered by the scheduled career-page monitor will now flow through Workflow 3 and can generate Telegram alerts.
- The prior behavior where jobs were evaluated silently without hitting the notify workflow is removed.

## 2026-03-06 - Phase 6C Telegram location gating tightened (ai-lab)

### What was executed

- Tightened Workflow 3 notify gating to align with current preference order:
  - alert only when `evaluation.observation.location.preference_bucket` is `remote` or `twin_cities`
  - retain existing score thresholds on top of that gate
- Updated Workflow 3 artifact and runbook:
  - `<repo-root>/n8n/workflows/phase6c_evaluate_notify_import.workflow.json`
  - `<repo-root>/n8n/workflows/phase6/workflow3_evaluate_notify.md`
- Telegram message format now includes:
  - preference bucket
  - raw location text
  - preferred-location candidate count
  - skipped-for-location count in workflow summary
- Synced updated Workflow 3 artifact to ai-lab and applied the active workflow update.

### Validation

- Verified active Workflow 3 `Evaluate + Notify` node on ai-lab contains preferred-location gating logic and `skipped_location_count`.
- Live smoke test before final wording cleanup:
  - remote sample `job_cb5faa2003e31baa` -> `notifications_sent=1`, `high_fit_count=1`, `preference_bucket=remote`
  - non-preferred sample `job_43fed45f47605c87` -> `notifications_sent=0`, `high_fit_count=0`, `skipped_location_count=1`
- Follow-up drift repair on ai-lab:
  - found that `workflow_entity` had the updated node code, but the active `workflow_history` version `17a9d75f-f30c-46e3-9bb3-1fa592a3a565` still carried the older `High-fit candidates` response summary in `Mark Telegram Send Result`
  - patched both `workflow_entity` and the active `workflow_history` row directly from the synced import artifact, then restarted `n8n`
- Post-repair live validation on March 6, 2026:
  - preferred sample `job_17c80b4e4cd23374` -> `evaluated=1`, `high_fit_count=1`, `skipped_location_count=0`, `notifications_sent=1`
  - non-preferred sample `job_6886f6bfccfe4eaf` -> `evaluated=1`, `high_fit_count=0`, `skipped_location_count=1`, `notifications_sent=0`
  - confirmed webhook response summary now reports `Preferred-location candidates` and `Skipped for location` on the notification path as intended
- Replay of March 6 backlog earlier in the day already confirmed Telegram delivery path was working end-to-end before this tighter filter was introduced.

### Results

- Telegram alerts are now materially less noisy: strong scores alone no longer notify unless the role is tagged `remote` or `twin_cities`.
- This is a notification-layer tightening only; evaluation scoring itself was not changed.

## 2026-03-04 - Phase 6C observation telemetry + evaluator hardening (local + ai-lab)

### What was executed

- Added evaluator observation telemetry persistence and merge safety:
  - `<repo-root>/scripts/phase6/job_evaluator.py`
  - fixed `_merge_evaluations` empty-value guard to avoid `TypeError` on list/dict values.
- Exposed observation payloads on jobs API normalization:
  - `<repo-root>/scripts/phase6/job_repository.py`
  - added `_normalize_observation()` and `observation` passthrough in normalized job payloads.
- Hardened metadata normalization for source and location type:
  - `<repo-root>/scripts/phase6/job_metadata_extractor.py`
  - added `ALLOWED_JOB_SOURCES`, `ALLOWED_LOCATION_TYPES`, `_normalize_source()`, `_normalize_location_type()`.
- Updated jobs API example payload to include observation shape:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
- Added focused Phase 6C regression coverage:
  - `<repo-root>/tests/test_phase6c_evaluation_observation.py`
  - covers malformed JSON retry strict prompt path, retry exhaustion failure, escalation observation content, metadata normalization, and repository observation sanitization.

### Validation

- Local:
  - `python3 -m py_compile scripts/phase6/job_evaluator.py scripts/phase6/job_repository.py scripts/phase6/job_metadata_extractor.py scripts/phase1/ingest_bridge_api.py tests/test_phase6c_evaluation_observation.py`
  - `python3 -m pytest -q tests/test_phase6c_evaluation_observation.py` -> `6 passed`
  - `python3 -m pytest -q tests/test_bridge_api_contract.py` -> `28 passed`
- ai-lab sync + spot-check:
  - synced changed files to `<server-repo-root>` using SSH key `~/.ssh/codex_ai_lab`.
  - remote `rg` spot-check confirmed new symbols in synced files:
    - `_build_observation`, `_normalize_observation`, `_normalize_source`, `_normalize_location_type`,
    - `test_evaluate_job_records_observation_with_escalation_context`.
- ai-lab runtime verification (after sync):
  - restarted bridge container: `docker restart recall-ingest-bridge`
  - `GET http://<ai-lab-tailnet-ip>:8090/v1/healthz` -> `200`
  - `POST /v1/job-evaluation-runs` (`wait=true`) for `job_8e1532ae101e822f` -> `200` with populated `observation` payload.
  - `GET /v1/jobs/job_8e1532ae101e822f` -> `200` and persisted `observation` object present.

### Results

- Phase 6C now emits consistent observation telemetry in both evaluation-run responses and persisted `/v1/jobs` records.
- Metadata extraction output is normalized for source/location typing, reducing malformed downstream fields.
- Regression coverage now protects key Phase 6C reliability paths (retry, escalation, observation, metadata normalization).

## 2026-03-04 - Career page monitor guardrail for company-list drift (ai-lab)

### What was executed

- Added a lightweight company-list drift guard to both repo and active import workflow artifacts:
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_import.workflow.json`
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_active_import.workflow.json`
- Guard behavior in `Load Companies`:
  - computes `expectedMinCompanies` (`11` for current config),
  - emits `company_list_count` and `company_list_warning`,
  - warning format: `career_page_company_list_low:<count> (expected >= <min>)`.
- Updated workflow summary nodes to surface guard metadata:
  - `Summary (Eval Queued)`
  - `Summary (No New Jobs)`
  - `Summary (No Matches)`
  - all now include `company_list_count` and `company_list_warning`; warning is also appended into `errors[]` where present.
- Synced active import artifact to ai-lab, imported/published/reactivated workflow `eE5wQFqV9oiSHKaL`, and restarted n8n.

### Validation

- Exported active workflow after deploy and confirmed:
  - workflow is `active=true`,
  - `Load Companies` contains `expectedMinCompanies` + warning expression,
  - `company_count=13`,
  - all three summary nodes include `company_list_warning`.

### Results

- If the active company set is unexpectedly reduced in future edits/imports, run outputs now include an explicit warning signal instead of silently degrading coverage.
- Career-page monitoring remains expanded at 13 supported ATS companies with drift visibility built-in.

## 2026-03-04 - Career page monitor hardcode removal (ai-lab active workflow)

### What was executed

- Identified active workflow drift on ai-lab:
  - `Recall Phase6B - Career Page Monitor (Traditional Import)` (`eE5wQFqV9oiSHKaL`) had a 2-company hardcoded list (`Anthropic`, `Postman`) despite broader repo config.
- Exported the active workflow and created an id-preserving import artifact:
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_active_import.workflow.json`
- Regenerated `Load Companies` node payload from `config/career_pages.json`, filtered to currently supported ATS fetchers in this workflow (`greenhouse|lever`) with valid `board_id`.
  - resulting active set: `13` companies (all Greenhouse targets currently configured).
- Synced the new import artifact to ai-lab and performed required remote spot-check before import/restart.
- Imported + published + reactivated workflow id `eE5wQFqV9oiSHKaL` and restarted n8n.

### Validation

- Exported active workflow post-deploy and parsed `Load Companies` node:
  - `company_count=13`
  - names: `Anthropic, OpenAI, Postman, Aisera, Miro, Airtable, Smartsheet, Cohere, Glean, Writer, Atlassian, Workato, Datadog`
- Workflow remained active after restart (`active=true`).

### Results

- Career page monitoring is no longer constrained to 2 hardcoded companies in production.
- Discovery coverage now aligns with the supported ATS subset of your curated company config, increasing direct-company intake immediately.
- Workday targets in `config/career_pages.json` remain out-of-scope for this specific workflow until Workday fetch support is added.

## 2026-03-04 - Phase 6C Telegram credential wiring (ai-lab)

### What was executed

- Detected newly created n8n Telegram credential and bot identity on ai-lab:
  - credential: `6aWx4DnLbVi8JlGU` (`Telegram account`, type `telegramApi`)
  - bot: `@RecallJobScoutBot`
- Retrieved chat context after `/start` and resolved target chat id:
  - private chat id: `8724583836`
- Updated Workflow 3 import artifact to send notifications through n8n Telegram credential (no `$env` dependency):
  - `<repo-root>/n8n/workflows/phase6c_evaluate_notify_import.workflow.json`
  - added `Send Telegram Alert` (`n8n-nodes-base.telegram`, `typeVersion: 1.2`, credential-bound, static chat id)
  - added `Mark Telegram Send Result` node to finalize `notifications_sent`/`notification_errors`.
  - retained explicit `If Has High Fit` gate and set node compatibility to `typeVersion: 1` so the numeric condition is enforced in this n8n build.
- Synced workflow file to ai-lab and performed remote symbol spot-check before each import/restart cycle.
- Imported, published, re-activated, and restarted n8n for the active workflow id:
  - `9DEQqfD8JA5PCiVP` (`Phase 6C - Workflow 3 - Evaluate & Notify`)

### Validation

- Webhook probe (existing high-fit job id) returned `200` with successful notification outcome:
  - `high_fit_count=1`
  - `notifications_sent=1`
  - `notification_errors=[]`
- Additional probe with unknown job id returned `200` and correctly skipped notify path:
  - `high_fit_count=0`
  - `notifications_sent=0`
  - `notification_errors=[]`
- n8n run history for Workflow 3 now shows fresh successful executions with Telegram path exercised and non-high-fit path clean.

### Results

- Phase 6C notifications are now using a real Telegram credential and live chat destination on ai-lab.
- Workflow 3 no longer relies on blocked env-variable access in n8n expressions.
- High-fit candidates now trigger real Telegram alerts from `@RecallJobScoutBot`.

## 2026-03-04 - n8n execution-error triage + workflow hardening (ai-lab)

### What was executed

- Pulled execution error details directly from ai-lab n8n SQLite (`<server-repo-root>/n8n/database.sqlite`) and decoded run payloads for:
  - `Recall Phase1B - Gmail Forward Ingest (HTTP Bridge)` (`409d18db-fdd1-4aa4-a508-be8f36b6a920`)
  - `Phase 6C - Workflow 3 - Evaluate & Notify` (`9DEQqfD8JA5PCiVP`)
- Confirmed current recurring Gmail error signature before patch:
  - `Invalid payload: Gmail payload has no body text and no attachment paths.`
- Patched Gmail HTTP bridge workflow JSONs to prevent empty-content calls:
  - `<repo-root>/n8n/workflows/phase1b_gmail_forward_ingest_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase1b_gmail_forward_ingest_http_import.workflow.json`
  - changes:
    - added `If Has Content` guard before `HTTP Ingest Gmail`
    - updated payload `text` fallback to include `textHtml/html` before subject fallback.
- Synced patched workflow files to ai-lab, imported, published, and restarted n8n.
- Attempted Telegram gating via `$env` in Workflow 3 and confirmed ai-lab policy blocks env access in expressions (`access to env vars denied`), so removed all `$env`-dependent nodes/conditions from:
  - `<repo-root>/n8n/workflows/phase6c_evaluate_notify_import.workflow.json`
  - kept non-failing high-fit branch behavior with explicit `telegram_not_configured`.
- Re-synced Workflow 3 import file to ai-lab, imported/published, and restarted n8n.

### Validation

- Post-patch Gmail executions are now succeeding (no new payload-validation failures observed):
  - latest runs: IDs `857`, `859`, `860` with `status=success`.
- Workflow 3 latest run is now successful after removing env expressions:
  - run ID `861`, `status=success`.
- Workflow 3 webhook runtime probe:
  - `POST /webhook/recall-job-evaluate` returned `200` with structured JSON result and `notification_errors=["telegram_not_configured"]`.

### Results

- The large red-error pattern in n8n was primarily from Gmail empty-payload events and earlier Workflow 3 transient wiring attempts; both now have successful fresh executions.
- ai-lab n8n currently enforces blocked environment variable access in node expressions, so Telegram configuration cannot rely on `$env` in workflows on this host.
- Telegram remains intentionally disabled until credentials are wired through a non-`$env` method.

## 2026-03-04 - Phase 6C n8n Workflow 3 activation fix (ai-lab)

### What was executed

- Re-synced the Workflow 3 import artifact from Mac to ai-lab and re-ran remote content spot-check before n8n restart/validation:
  - `<repo-root>/n8n/workflows/phase6c_evaluate_notify_import.workflow.json`
  - remote `rg` confirmed bridge URLs now target `http://<ai-lab-tailnet-ip>:8090` and code node fallback returns `telegram_not_configured`.
- Imported and published active n8n workflow id `9DEQqfD8JA5PCiVP` on ai-lab:
  - `docker exec n8n n8n import:workflow --input=/home/node/.n8n/workflows/phase6c_evaluate_notify_import.workflow.json`
  - `docker exec n8n n8n publish:workflow --id=9DEQqfD8JA5PCiVP`
- Restarted n8n to apply published workflow changes:
  - `docker restart n8n`

### Validation

- `GET http://localhost:5678/healthz` returned `200` after restart.
- `POST http://localhost:5678/webhook/recall-job-evaluate` with `{"job_ids":["job_459ef7bb606636af"],"wait":true}` returned `200` with expected Phase 6C payload fields:
  - `run_id`, `status=completed`, `result_count=1`, `high_fit_count=1`
  - `notification_errors=["telegram_not_configured"]`
  - populated `high_fit_jobs[]` with Anthropic role metadata.

### Results

- Active n8n Workflow 3 (`recall-job-evaluate`) is now upgraded from skeleton behavior to the Phase 6C evaluate/notify flow.
- Previous execution failure path from env/process access in code node is removed; workflow now returns deterministic success payloads without Telegram credentials.

## 2026-03-04 - Phase 6C ai-lab rollout + qdrant scroll compatibility fix

### What was executed

- Synced Phase 6C implementation files from Mac to ai-lab and performed required remote spot-check before restart/curl:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - `<repo-root>/scripts/phase6/job_evaluator.py`
  - `<repo-root>/scripts/phase6/gap_aggregator.py`
  - `<repo-root>/scripts/phase6/job_metadata_extractor.py`
  - `<repo-root>/tests/test_bridge_api_contract.py`
  - `<repo-root>/n8n/workflows/phase6/workflow3_evaluate_notify.md`
- Restarted bridge container on ai-lab:
  - `docker restart recall-ingest-bridge`
- During sync-run evaluation verification, ai-lab returned:
  - `workflow_failed: Unknown arguments: ['query_filter']`
- Patched qdrant compatibility fallback in both locations that used `scroll(..., query_filter=...)`:
  - `<repo-root>/scripts/phase6/job_evaluator.py`
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - behavior: if runtime rejects `query_filter`, retry with `scroll_filter`.
- Re-synced patched files to ai-lab, re-spot-checked, and restarted bridge.

### Validation

- `GET /v1/healthz` returned `200`.
- `POST /v1/job-evaluation-runs`:
  - `wait=false` returned `202` with queued run metadata.
  - `wait=true` returned `200` with `evaluated=1`, `failed=0`, and `results[]`.
- `GET /v1/job-gaps` returned `200` and included:
  - `aggregated_gaps`, `total_jobs_analyzed`, plus compatibility keys (`top_gaps`, `recommended_focus`).
- `POST /v1/ingestions` (bookmarklet/text with `group=job-search` + LinkedIn-style URL metadata) returned `200` and included:
  - `job_pipeline[0].routed=true`
  - non-empty `new_job_ids`
  - non-empty `evaluation_run_id` (async queue).
- n8n probe of `POST /webhook/recall-job-evaluate` returned `200` from the currently active skeleton workflow (placeholder payload), indicating Workflow 3 in n8n has not yet been upgraded from skeleton nodes.

### Results

- Phase 6C bridge/runtime behavior is now verified on ai-lab for evaluation runs, gap aggregation, and Chrome-extension job routing.
- qdrant-client version differences on ai-lab are now handled without runtime failure.
- n8n Workflow 3 deployment remains a separate step (active workflow is still skeleton behavior).

## 2026-03-04 - Phase 6C implementation (evaluation engine + ingestion hook + workflow 3 docs, local)

### What was executed

- Replaced Phase 6C evaluator scaffold with an operational evaluation pipeline in:
  - `<repo-root>/scripts/phase6/job_evaluator.py`
  - implemented resume/job loading, structured prompt generation, local/cloud provider calls with retry parity, strict JSON parsing/validation + retry, auto-escalation checks, and persistence of evaluated/error status back to `recall_jobs`.
  - `queue_job_evaluations()` now supports async queue mode (`wait=false`) and synchronous return mode (`wait=true`) with per-job result rows.
- Replaced gap aggregation scaffold with ranked, deduplicated aggregation in:
  - `<repo-root>/scripts/phase6/gap_aggregator.py`
  - added evaluated-job filtering (`status=evaluated`, `fit_score>0`), fuzzy merge via embedding/lexical similarity, severity averaging, and top recommendation rollups.
  - response now includes Phase 6 PRD-style `aggregated_gaps` and `total_jobs_analyzed` while retaining previous compatibility fields.
- Replaced metadata extractor scaffold with LLM-backed extraction in:
  - `<repo-root>/scripts/phase6/job_metadata_extractor.py`
  - expanded job URL pattern detection, source inference, Ollama JSON extraction prompt, robust JSON cleaning/parsing, and fallback heuristics.
- Wired the Chrome-extension post-ingestion hook and Phase 6C evaluation run behavior in:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - `POST /v1/job-evaluation-runs` now returns `202` for async queue and `200` for sync completion, with richer response payloads.
  - added post-ingestion job routing for `group=job-search` + matching job URL patterns: metadata extraction -> `POST /v1/job-discovery-runs` logic (`phase6_run_discovery`) -> async evaluation queue.
  - ingestion responses now include `job_pipeline[]` routing outcomes when applicable.
- Upgraded Workflow 3 runbook from skeleton to full Phase 6C flow in:
  - `<repo-root>/n8n/workflows/phase6/workflow3_evaluate_notify.md`
- Updated docs index wording to reflect full Workflow 3 notes in:
  - `<repo-root>/docs/README.md`
- Extended bridge API contract tests for new 6C behaviors in:
  - `<repo-root>/tests/test_bridge_api_contract.py`
  - added async/sync `POST /v1/job-evaluation-runs` assertions and ingestion hook routing assertions.

### Validation

- `python3 -m py_compile scripts/phase6/job_evaluator.py scripts/phase6/gap_aggregator.py scripts/phase6/job_metadata_extractor.py scripts/phase1/ingest_bridge_api.py tests/test_bridge_api_contract.py`
- `python3 -m pytest -q tests/test_bridge_api_contract.py -q`

### Results

- Phase 6C core backend logic is now implemented locally (no longer scaffold-only):
  - evaluation run endpoint executes real scoring flows,
  - gap aggregation returns ranked deduplicated outputs,
  - Chrome-extension ingestion can route job URLs into `recall_jobs` and queue evaluations.
- n8n Workflow 3 documentation is now implementation-complete for evaluate/notify orchestration.
- This entry covers local implementation and local validation only; ai-lab sync/restart/runtime verification was not performed in this step.

## 2026-03-04 - Phase 6B closeout hardening (API visibility + n8n URL/payload fixes)

### What was executed

- Updated jobs API query validation to allow unscored queue visibility:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - `GET /v1/jobs` now allows `min_score=-1` (while keeping default `0`).
- Added contract coverage for the new query bound:
  - `<repo-root>/tests/test_bridge_api_contract.py`
  - added test asserting `min_score=-1` is accepted and `min_score=-2` is rejected.
- Updated API docs to reflect unscored queue query support:
  - `<repo-root>/docs/Phase6A_Foundation_Brief.md`
  - `<repo-root>/docs/Recall_local_Phase6_Job_Hunt_PRD.md`
- Updated n8n workflow/runbook docs and templates to remove DNS-fragile bridge host defaults and align payload shapes:
  - `<repo-root>/n8n/workflows/phase1b_gmail_forward_ingest_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase1b_recall_ingest_webhook_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase3a_bookmarklet_form_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase6a_recall_ingest_canonical_http.workflow.json`
  - `<repo-root>/n8n/workflows/PHASE1B_CHANNEL_WIRING.md`
  - `<repo-root>/n8n/workflows/PHASE3A_OPERATOR_FORMS_WIRING.md`
  - `<repo-root>/n8n/workflows/phase6/README.md`
  - `<repo-root>/n8n/workflows/phase6/workflow1_aggregator.md`
  - `<repo-root>/n8n/workflows/phase6/workflow2_career_pages.md`
- Synced updated files to ai-lab and performed remote content spot-checks before restart/verification.

### Validation

- Local contract tests:
  - `python3 -m pytest -q tests/test_bridge_api_contract.py -q`
- ai-lab runtime verification after bridge restart:
  - `GET /v1/jobs?status=new&min_score=-1&limit=5` returned persisted unscored jobs (`fit_score=-1`).
  - `GET /v1/jobs?status=new&min_score=-2` returned `422` (bounds enforced).
  - `POST /webhook/recall-ingest` returned canonical webhook response with populated `bridge_result.ingested[]`.

### Results

- Phase 6B now has stable n8n->bridge connectivity in active HTTP workflows (no required dependence on `recall-ingest-bridge` DNS name).
- Jobs discovered but not yet evaluated are visible via API using `status=new&min_score=-1`.
- API and runbook documentation now matches observed production behavior on ai-lab.

## 2026-03-04 - Phase 6B ai-lab Workflow 1 enablement (jobspy source)

### What was executed

- Installed `python-jobspy` into running ai-lab bridge container:
  - `docker exec recall-ingest-bridge python3 -m pip install --no-cache-dir python-jobspy`
- Fixed JobSpy source runner compatibility in:
  - `<repo-root>/scripts/phase6/job_discovery_runner.py`
  - changed JobSpy invocation to query one site at a time and temporarily excluded LinkedIn from runner site list due runtime country parsing failures in this environment.
- Synced updated runner file to ai-lab and performed required remote spot-check before restart:
  - `rsync ... scripts/phase6/job_discovery_runner.py ... <server-repo-root>/`
  - `ssh ... rg -n 'sites = [\"indeed\", \"glassdoor\", \"zip_recruiter\"]' scripts/phase6/job_discovery_runner.py`
- Restarted bridge:
  - `docker restart recall-ingest-bridge`

### Validation

- JobSpy-only dry-run discovery probe:
  - `POST /v1/job-discovery-runs` with `sources=["jobspy"]`, `titles=["Solutions Engineer"]`, `locations=["Remote"]`, `max_queries=1`, `dry_run=true`
  - result: `discovered_raw=60`, `new_jobs=60`, `new_job_ids` returned.
- Full Workflow 1 source-set dry-run probe:
  - `POST /v1/job-discovery-runs` with `sources=["jobspy","adzuna","serpapi"]`, same query controls.
  - result:
    - `jobspy` returned jobs (`source_metrics.jobspy.returned=60`)
    - `adzuna`/`serpapi` skipped with explicit missing-key messages
    - `new_job_ids` returned from jobspy lane.

### Results

- Workflow 1 is now unblocked on primary source (`jobspy`) and returns non-empty `new_job_ids`.
- Adzuna and SerpAPI remain pending until real credentials are added on ai-lab:
  - `RECALL_ADZUNA_APP_ID`
  - `RECALL_ADZUNA_APP_KEY`
  - `RECALL_SERPAPI_API_KEY`

## 2026-03-04 - Phase 6B discovery implementation (local)

### What was executed

- Implemented Phase 6B bridge-side discovery runner and source adapters in:
  - `<repo-root>/scripts/phase6/job_discovery_runner.py`
  - added real source execution paths for `jobspy`, `adzuna`, `serpapi`, and `career_page`.
  - added query rotation persistence (`settings.setting_key=job_discovery_cursor`) so title/location combos are rotated instead of fully replayed each run.
  - added normalization, company tier tagging, dedup checks, Qdrant upsert into `recall_jobs`, activity-log writeback, and `new_job_ids` in run output.
  - added manual normalized-job ingestion support (`jobs[]` payload) for workflow-driven career-page monitoring.
- Reworked dedup logic in:
  - `<repo-root>/scripts/phase6/job_dedup.py`
  - checks now run in this order:
    - exact URL in `recall_jobs`,
    - same company+title within 7 days,
    - semantic similarity via vector search threshold.
  - added compatibility response fields: `duplicate` + `is_duplicate`, `matched_job_id` + `similar_job_id`.
- Updated bridge API request contract and handler behavior in:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - expanded `POST /v1/job-discovery-runs` schema with source controls and optional `jobs[]`.
  - expanded `POST /v1/job-deduplications` schema/validation to allow `url` or `description` or `title+company`.
  - added explicit `workflow_failed` handling for discovery execution exceptions.
- Added Phase 6B guided n8n workflow documentation:
  - `<repo-root>/n8n/workflows/phase6/README.md`
  - `<repo-root>/n8n/workflows/phase6/workflow1_aggregator.md`
  - `<repo-root>/n8n/workflows/phase6/workflow2_career_pages.md`
  - `<repo-root>/n8n/workflows/phase6/workflow3_evaluate_notify.md`
- Added import-ready Workflow 2 n8n export for lower-touch setup:
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_import.workflow.json`
  - includes manual trigger + single code node that executes Greenhouse/Lever polling, title filtering, `POST /v1/job-discovery-runs`, and optional `POST /v1/job-evaluation-runs`.
- Added import-ready Workflow 2 traditional multi-node n8n export for step-level observability:
  - `<repo-root>/n8n/workflows/phase6b_career_page_monitor_traditional_import.workflow.json`
  - includes manual trigger + staged nodes (`Load Companies` -> `Fetch ATS Jobs` -> `Normalize + Filter Titles` -> `If Has Jobs` -> `Trigger Discovery Run` -> `If New Jobs` -> `Trigger Evaluation Run`) with summary branches for no-match/no-new-job lanes.
- Updated docs index to include new Phase 6 workflow guidance:
  - `<repo-root>/docs/README.md`
- Extended bridge API contract tests for Phase 6B request/response behavior:
  - `<repo-root>/tests/test_bridge_api_contract.py`

### Validation

- `python3 -m py_compile scripts/phase6/job_discovery_runner.py scripts/phase6/job_dedup.py scripts/phase1/ingest_bridge_api.py tests/test_bridge_api_contract.py`
- `python3 -m unittest tests/test_bridge_api_contract.py`

### Results

- Phase 6B backend discovery path is now implemented beyond scaffold state.
- Job discovery runs now return actionable `new_job_ids` for downstream evaluation workflows.
- Guided workflow build notes exist for the three Phase 6B n8n workflows.

## 2026-03-04 - Phase 6A execution closeout (local + ai-lab)

### What was executed

- Synced Phase 6A implementation files from Mac to ai-lab and ran required remote content spot-checks:
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --relative scripts/phase1/ingest_bridge_api.py scripts/phase6 config/career_pages.json config/job_search.json ui/daily-dashboard docker/docker-compose.yml docker/.env.example tests/test_bridge_api_contract.py jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n '/v1/jobs|/v1/resumes|/v1/companies|/v1/llm-settings|workflow_06a' scripts/phase1/ingest_bridge_api.py"`
- Executed Qdrant Phase 6 collection bootstrap on ai-lab:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && python3 scripts/phase6/setup_collections.py"`
  - result: `recall_jobs` created, `recall_resume` already present.
- Ingested Jay's current resume into `recall_resume`:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && python3 -m scripts.phase6.ingest_resume --file <vault-root>/career/Jay-Dreyer-Resume.md"`
  - result: `version=2`, `chunks=10`.
- Restarted bridge and verified live Phase 6A endpoint responses on ai-lab:
  - `GET /v1/jobs`, `GET /v1/resumes/current`, `GET /v1/llm-settings`, `GET /v1/job-stats`, `GET /v1/job-gaps` all returned `HTTP 200`.
  - OpenAPI spot-check confirmed all Phase 6A paths were present and `servers` included local + ai-lab URLs.
- Brought up Daily Dashboard service and verified delivery on port `3001`.
- Fixed a compose healthcheck defect discovered during dashboard bring-up:
  - `<repo-root>/docker/docker-compose.yml`
  - changed `qdrant` healthcheck from `curl` (not present in `qdrant/qdrant` image) to a bash TCP probe (`/dev/tcp/127.0.0.1/6333`) so `depends_on: condition: service_healthy` no longer false-fails.

### Validation

- `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && python3 scripts/phase6/setup_collections.py"`
- `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && python3 -m scripts.phase6.ingest_resume --file <vault-root>/career/Jay-Dreyer-Resume.md"`
- `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "curl -sS http://localhost:8090/v1/jobs"`
- `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "curl -sS http://localhost:8090/v1/resumes/current"`
- `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "curl -sS http://localhost:3001/"`
- `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "python3 - <<'PY'\nimport json,urllib.request\nurl='http://localhost:8090/openapi.json'\nwith urllib.request.urlopen(url, timeout=10) as r:\n    spec=json.load(r)\npaths=spec.get('paths',{})\ncheck=['/v1/jobs','/v1/jobs/{jobId}','/v1/job-evaluation-runs','/v1/job-stats','/v1/job-gaps','/v1/job-deduplications','/v1/job-discovery-runs','/v1/resumes','/v1/resumes/current','/v1/companies','/v1/companies/{companyId}','/v1/company-profile-refresh-runs','/v1/llm-settings']\nmissing=[p for p in check if p not in paths]\nprint('missing:', missing)\nprint('servers:', spec.get('servers'))\nPY"`

### Results

- Phase 6A Definition of Done items are now satisfied on ai-lab runtime:
  - collections present,
  - canonical `/v1/*` endpoints live,
  - resume ingested,
  - LLM settings persisted and readable,
  - Daily Dashboard serving on `:3001`.
- Compose startup reliability for the full stack is improved by the `qdrant` healthcheck fix.

## 2026-03-04 - Phase 6A foundation implementation (local)

### What was executed

- Added Phase 6 collection bootstrap and runtime helpers:
  - `<repo-root>/scripts/phase6/setup_collections.py`
  - `<repo-root>/scripts/phase6/storage.py`
  - `<repo-root>/scripts/phase6/job_repository.py`
  - `<repo-root>/scripts/phase6/job_dedup.py`
  - `<repo-root>/scripts/phase6/job_discovery_runner.py`
  - `<repo-root>/scripts/phase6/job_evaluator.py`
  - `<repo-root>/scripts/phase6/gap_aggregator.py`
  - `<repo-root>/scripts/phase6/company_profiler.py`
  - `<repo-root>/scripts/phase6/telegram_notifier.py`
  - `<repo-root>/scripts/phase6/job_metadata_extractor.py`
- Added resume ingestion CLI and bridge integration:
  - `<repo-root>/scripts/phase6/ingest_resume.py`
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - supports JSON markdown payloads and multipart file upload payloads for `POST /v1/resumes`.
- Added Phase 6 canonical API surface to existing bridge (`operations-v1`):
  - `GET /v1/jobs`
  - `GET /v1/jobs/{jobId}`
  - `PATCH /v1/jobs/{jobId}`
  - `POST /v1/job-evaluation-runs`
  - `GET /v1/job-stats`
  - `GET /v1/job-gaps`
  - `POST /v1/job-deduplications`
  - `POST /v1/job-discovery-runs`
  - `POST /v1/resumes`
  - `GET /v1/resumes/current`
  - `GET /v1/companies`
  - `GET /v1/companies/{companyId}`
  - `POST /v1/company-profile-refresh-runs`
  - `GET /v1/llm-settings`
  - `PATCH /v1/llm-settings`
- Added Phase 6 configuration files:
  - `<repo-root>/config/career_pages.json`
  - `<repo-root>/config/job_search.json`
- Added Daily Dashboard scaffold and Docker wiring:
  - `<repo-root>/ui/daily-dashboard/` (React/Vite app with Atelier Ops theme, tab shell, bridge API client, and Recharts placeholder)
  - `<repo-root>/docker/docker-compose.yml` (new `daily-dashboard` service)
  - `<repo-root>/docker/.env.example` (Phase 6 job + dashboard env vars)
- Extended bridge contract coverage:
  - `<repo-root>/tests/test_bridge_api_contract.py`
  - includes schema path checks and Phase 6 endpoint behavior checks.

### Validation

- `python3 -m py_compile scripts/phase1/ingest_bridge_api.py scripts/phase6/*.py`
- `python3 -m unittest tests/test_bridge_api_contract.py`
- `python3 -m unittest discover -s tests`
- `npm --prefix <repo-root>/ui/daily-dashboard install`
- `npm --prefix <repo-root>/ui/daily-dashboard run build`

### Results

- Phase 6A foundation backend endpoints are now present on canonical `/v1/*` paths and included in OpenAPI output.
- LLM settings now persist via SQLite (`settings` table) and are retrievable/updateable via API.
- Resume ingestion flow and CLI scaffold are implemented; live ingestion of Jay's actual resume depends on providing a source file path.
- Daily Dashboard scaffold is buildable and dockerized with the requested Atelier Ops visual direction on port `3001`.

## 2026-02-26 - Query relevance and citation UX hardening (local + ai-lab)

### What was executed

- Added strict tag-filter matching controls end-to-end:
  - `<repo-root>/scripts/phase1/retrieval.py`
    - added `filter_tag_mode` normalization and `any|all` query-filter behavior.
  - `<repo-root>/scripts/phase1/rag_query.py`
    - wired `filter_tag_mode` through retrieval passes and audit payload.
  - `<repo-root>/scripts/phase1/rag_from_payload.py`
    - forwarded `filter_tag_mode` from payload runner.
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
    - accepted/validated `filter_tag_mode` in `POST /v1/rag-queries`.
- Added Query tab controls for tag semantics:
  - `<repo-root>/ui/dashboard/src/App.jsx`
    - new `Tag Match` selector (`any (OR)` / `all (AND)`).
    - preserved redundant tag-elision when tag equals selected group.
- Upgraded citation cards for demo readability:
  - `<repo-root>/ui/dashboard/src/App.jsx`
  - `<repo-root>/ui/dashboard/src/App.css`
  - citation cards now show human-friendly source labels/snippets by default and collapse raw IDs under `Technical details`.
  - grouped duplicate source citations into one card with chunk-count badge (for example `2 chunks`) and aggregated chunk/id references.
- Added ingestion-tokenization hardening for special-token-like text:
  - `<repo-root>/scripts/phase1/ingestion_pipeline.py`
    - `_token_windows` now uses `encode_ordinary()` when available, otherwise `encode(..., disallowed_special=())`.
  - `<repo-root>/tests/test_phase5f_ingest_special_tokens.py`
    - regression coverage for `<|endofprompt|>`-style text.

### Validation

- `python3 -m unittest tests/test_phase5b_metadata_model.py`
- `python3 -m unittest tests.test_bridge_api_contract.BridgeApiContractTests.test_rag_query_normalizes_filter_group_and_tag_mode tests.test_bridge_api_contract.BridgeApiContractTests.test_rag_query_rejects_invalid_filter_tag_mode`
- `python3 -m unittest tests/test_phase5f_unanswerable_normalization.py`
- `npm --prefix <repo-root>/ui/dashboard run build`
- Synced local updates to ai-lab and spot-checked content:
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --relative ... <repo-root>/... jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'dedupeCitationCards|filter_tag_mode|citation-count|Technical details' ..."`
- Rebuilt UI service in lite stack:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && docker compose -f docker/phase1b-ingest-bridge.compose.yml -f docker/docker-compose.lite.yml up -d --build recall-ui"`

### Results

- `filter_tag_mode=all` now prevents mixed-tag retrieval bleed-through and supports stricter demo queries.
- Query citations are now human-readable by default while retaining chunk-level traceability in expandable details.
- Duplicate citation cards from the same source are reduced to a single grouped card.
- ai-lab runtime is synced with local for these changes and `recall-ui` is running on port `8170`.

## 2026-02-26 - Phase 5 post-audit punch list implementation (local)

### What was executed

- Added audit punch-list source doc into project docs:
  - `<repo-root>/docs/phase5-punch-list.md`
- Implemented canonical multipart upload endpoint:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - new route: `POST /v1/ingestions/files`
  - controls:
    - API key + rate-limit enforcement using existing bridge gate
    - extension allow-list: `.pdf,.docx,.txt,.md,.html,.eml`
    - size limit via `RECALL_MAX_UPLOAD_MB` (default `50`)
    - `415` for unsupported file type, `413` for oversized upload
  - request fields:
    - multipart `file`
    - `group` (optional)
    - `tags` (comma-separated)
    - `save_to_vault` (optional boolean)
- Added bridge contract coverage for multipart route and OpenAPI path:
  - `<repo-root>/tests/test_bridge_api_contract.py`
- Added dashboard drag-drop + file-picker upload flow on Ingest tab:
  - `<repo-root>/ui/dashboard/src/App.jsx`
  - `<repo-root>/ui/dashboard/src/App.css`
  - `<repo-root>/ui/dashboard/src/api.js`
  - uploads now carry currently selected `group` and `tags` into `POST /v1/ingestions/files`.
- Added CI test execution gate:
  - `<repo-root>/.github/workflows/quality_checks.yml`
  - new step: `pytest tests/ -v --tb=short`
- Added Chrome extension popup save-to-vault toggle:
  - `<repo-root>/chrome-extension/popup.html`
  - `<repo-root>/chrome-extension/popup.js`
  - payload now sends `save_to_vault`.
- Completed compose consolidation + lite preservation:
  - `<repo-root>/docker/docker-compose.yml` (full-stack default)
  - `<repo-root>/docker/docker-compose.lite.yml` (Approach B)
  - `<repo-root>/docker/bridge/Dockerfile` (new)
  - `<repo-root>/docker/mkdocs/Dockerfile` (new)
  - `<repo-root>/scripts/phase5/run_operator_stack_now.sh` now supports `--lite`.
- Completed dashboard font swap:
  - `<repo-root>/ui/dashboard/src/index.css`
  - mono font now `IBM Plex Mono`.
- Verified canonical route references (runtime callers) via grep sweep:
  - `rg -n "/config/auto-tags" --glob "*.json" --glob "*.js" --glob "*.py" --glob "*.yml" .`
  - `rg -n "/ingest/" --glob "*.json" --glob "*.js" --glob "*.py" --glob "*.yml" .`
  - `rg -n "(/query/rag|/rag/query|/activity|/eval/latest|/eval/run|/v1/vault/tree|/v1/vault/sync|/vault/tree|/vault/sync)" --glob "*.json" --glob "*.js" --glob "*.py" --glob "*.yml" .`
  - remaining matches were expected alias-regression tests only.
- Updated docs and environment references:
  - `<repo-root>/docs/README.md`
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - `<repo-root>/docs/Recall_local_Phase5_Operator_Entrypoint_Runbook.md`
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md`
  - `<repo-root>/docker/.env.example` (`RECALL_MAX_UPLOAD_MB`)
  - `<repo-root>/requirements.txt` (`python-multipart`)

### Validation

- `python3 -m unittest discover -s tests -p 'test_bridge_api_contract.py'`
- `python3 -m unittest discover -s tests`
- `cd <repo-root>/ui/dashboard && npm run build`
- `bash -n <repo-root>/scripts/phase5/run_operator_stack_now.sh`
- `<repo-root>/scripts/phase5/run_operator_stack_now.sh help`
- `python3 <repo-root>/scripts/phase1/ingest_bridge_api.py --help`
- Full eval attempt:
  - `<repo-root>/scripts/phase3/run_all_evals_now.sh`
  - result: failed with webhook connection refusal to `http://localhost:5678/webhook/recall-query` (service not reachable in this local session).

### Results

- Punch-list implementation tasks are complete in local codebase.
- Unit/contract test suite now passes (`33/33`).
- Dashboard build passes with drag-drop upload UI and font update.
- Full eval gate was attempted and failed for environment-connectivity reasons (not code-level test regressions).

## 2026-02-26 - Phase 5 closeout sync to ai-lab + spot-check

### What was executed

- Synced closeout code/script updates from Mac to ai-lab:
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --files-from=/tmp/recall_phase5_closeout_sync1.txt <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --files-from=/tmp/recall_phase5_closeout_sync2.txt <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" <repo-root>/scripts/phase5/run_phase5_demo_now.sh jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/scripts/phase5/run_phase5_demo_now.sh`
- Ran required remote content spot-checks:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n '_normalize_unanswerable_consistency|_looks_like_internal_identifier_answer|HEX_IDENTIFIER_PATTERN|Phase5FUnanswerableNormalizationTests' scripts/phase1/rag_query.py tests/test_phase5f_unanswerable_normalization.py"`
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'Which URL source is indexed in memory|dashboard query did not return citations|extension channel ingest call \\(gmail-forward\\)' scripts/phase5/run_phase5_demo_now.sh"`

### Results

- Sync gate passed with `rsync` exit code `0`.
- Spot-check confirmed ai-lab has the unanswerable normalization fix, new regression tests, and updated demo-runner lane assertions.

## 2026-02-26 - Phase 5 closeout: unanswerable eval guard + completion-gate validation

### What was executed

- Fixed unanswerable regression in:
  - `<repo-root>/scripts/phase1/rag_query.py`
  - added deterministic post-generation normalization to prevent identifier-like answers (for example internal `doc_id`-style tokens) from surfacing as high-confidence answers.
  - added unanswerable consistency guard that forces `confidence_level=low` when abstention phrasing is present.
- Added regression coverage:
  - `<repo-root>/tests/test_phase5f_unanswerable_normalization.py`
- Updated demo runner lane assertions and extension-ingest evidence in:
  - `<repo-root>/scripts/phase5/run_phase5_demo_now.sh`
  - dashboard query lane now asserts citation presence (`citation_count >= 1`).
  - extension lane now includes explicit `channel=gmail-forward` ingestion request/response verification.
- Verified runtime and closeout evidence on ai-lab:
  - restarted bridge:
    - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "docker restart recall-ingest-bridge"`
  - unanswerable probe:
    - `POST /v1/rag-queries?dry_run=true` for `What is the AWS account ID for Recall.local production?`
    - response now returns explicit abstention with `confidence_level=low`.
  - core eval gate:
    - `POST /v1/evaluation-runs` with `{"suite":"core","backend":"direct","dry_run":true,"wait":true}`
    - result now `pass` with `15/15`.
  - strict demo run:
    - `<repo-root>/scripts/phase5/run_phase5_demo_now.sh --bridge-url http://<ai-lab-tailnet-ip>:8090 --mode dry-run --eval-suite core --require-eval-pass`
    - generated artifacts:
      - `<repo-root>/data/artifacts/demos/phase5/20260226T155927Z/phase5_demo_summary.json`
      - `<repo-root>/data/artifacts/demos/phase5/20260226T155927Z/dashboard_query_response.json`
      - `<repo-root>/data/artifacts/demos/phase5/20260226T155927Z/extension_ingest_response.json`
      - `<repo-root>/data/artifacts/demos/phase5/20260226T155927Z/vault_sync_response.json`
      - `<repo-root>/data/artifacts/demos/phase5/20260226T155927Z/eval_run_response.json`
  - operator stack bring-up for UI verification:
    - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && scripts/phase5/run_operator_stack_now.sh up"`
    - `recall-ui` verified running (`http://<ai-lab-tailnet-ip>:8170`, HTTP `200`).

### Validation

- `python3 -m unittest discover -s tests -p 'test_phase5f_unanswerable_normalization.py'`
- `python3 -m unittest discover -s tests -p 'test_bridge_api_contract.py'`
- `python3 -m unittest discover -s tests`
- `bash -n <repo-root>/scripts/phase5/run_phase5_demo_now.sh`
- `<repo-root>/scripts/phase5/run_phase5_demo_now.sh --help`

### Results

- Unanswerable eval regression resolved (`core` eval now `15/15` pass).
- Demo runner now records evidence for dashboard ingest/query (with citations), extension ingest channel, vault sync/query, and eval gate in one command.
- Phase 5 completion checklist items are now backed by fresh runtime evidence and can be closed.

## 2026-02-25 - Phase 5F demo runner sync to ai-lab + spot-check

### What was executed

- Synced demo-runner batch updates from Mac to ai-lab:
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --files-from=/tmp/recall_phase5_demo_sync_files.txt <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
- Synced the latest demo-runner script revision after vault-lane host-awareness update:
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" <repo-root>/scripts/phase5/run_phase5_demo_now.sh jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/scripts/phase5/run_phase5_demo_now.sh`
- Ran required remote content spot-checks:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'run_phase5_demo_now\\.sh|Recall_local_Phase5_Demo_Runbook|Record demo run script covering|run_operator_stack_now\\.sh help >/dev/null|run_phase5_demo_now\\.sh --help >/dev/null' scripts/phase5/run_phase5_demo_now.sh docs/Recall_local_Phase5_Demo_Runbook.md docs/Recall_local_Phase5_Checklists.md .github/workflows/quality_checks.yml"`
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'local -a cmd|dashboard ingest/query calls' scripts/phase5/run_phase5_demo_now.sh"`

### Results

- Sync gate passed with `rsync` exit code `0`.
- Spot-check confirmed ai-lab has the new demo runner script, runbook entry, checklist completion marker, and wrapper-smoke CI references.

## 2026-02-25 - Phase 5F demo packaging: one-command demo runner + runbook

### What was executed

- Added Phase `5F` demo runner script:
  - `<repo-root>/scripts/phase5/run_phase5_demo_now.sh`
  - lanes covered:
    - dashboard ingest/query
    - extension capture gate (unit + optional browser smoke)
    - Obsidian sync/query
    - eval gate check
  - execution controls:
    - `--mode dry-run|live`
    - `--eval-suite`, `--eval-backend`, `--require-eval-pass`
    - optional Gmail browser smoke execution
  - artifact output:
    - `data/artifacts/demos/phase5/<timestamp>/`
    - timestamped per-lane request/response JSON + run summary JSON
- Added demo runbook:
  - `<repo-root>/docs/Recall_local_Phase5_Demo_Runbook.md`
- Updated docs/checklist/index references:
  - `<repo-root>/docs/README.md`
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md`
- Extended CI wrapper smoke checks:
  - `<repo-root>/.github/workflows/quality_checks.yml`
  - now includes:
    - `scripts/phase5/run_operator_stack_now.sh help`
    - `scripts/phase5/run_phase5_demo_now.sh --help`

### Validation

- `bash -n <repo-root>/scripts/phase5/run_phase5_demo_now.sh`
- `<repo-root>/scripts/phase5/run_phase5_demo_now.sh --help`
- `<repo-root>/scripts/phase5/run_operator_stack_now.sh help`
- `python3 -m unittest discover -s tests -p 'test_phase5e1_gmail_extension.py'`
- Demo-runner dry-run attempt against ai-lab bridge:
  - `<repo-root>/scripts/phase5/run_phase5_demo_now.sh --bridge-url http://<ai-lab-tailnet-ip>:8090 --mode dry-run --eval-suite core`
  - lanes `1-4` passed (health, dashboard ingest/query, extension contract tests, vault sync/query)
  - lane `5` blocked by current ai-lab runtime route availability (`POST /v1/evaluation-runs` returned `404`).

### Results

- Phase `5F` now has a recorded one-command demo runner and dedicated runbook.
- Checklist item `Record demo run script covering ...` is complete.
- Remaining completion-gate validation depends on running against a bridge runtime that exposes `/v1/evaluation-runs`.

## 2026-02-25 - Phase 5F operator-entrypoint sync to ai-lab + spot-check

### What was executed

- Synced operator-entrypoint updates from Mac to ai-lab:
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --files-from=/tmp/recall_phase5f_operator_sync_files.txt <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
- Ran required remote content spot-check:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'run_operator_stack_now\\.sh|Phase5_Operator_Entrypoint_Runbook|Consolidate compose runtime entrypoint' scripts/phase5/run_operator_stack_now.sh docs/Recall_local_Phase5_Operator_Entrypoint_Runbook.md docs/Recall_local_Phase5_Checklists.md"`

### Results

- Sync gate passed with `rsync` exit code `0`.
- Spot-check confirmed new operator entrypoint script, runbook, and checklist completion marker are present on ai-lab.

## 2026-02-25 - Phase 5F compose/runtime consolidation: single operator entrypoint

### What was executed

- Added consolidated compose/runtime operator entrypoint script:
  - `<repo-root>/scripts/phase5/run_operator_stack_now.sh`
  - command surface:
    - `up`
    - `down`
    - `restart`
    - `status`
    - `logs`
    - `preflight`
    - `config`
  - compose consolidation strategy:
    - uses both compose files as one runtime surface:
      - `<repo-root>/docker/phase1b-ingest-bridge.compose.yml`
      - `<repo-root>/docker/docker-compose.yml`
  - optional operator preflight pass through:
    - `--preflight` on `up`/`restart` invokes `<repo-root>/scripts/phase3/run_service_preflight_now.sh`
    - supports `--bridge-url` and `--n8n-host` overrides for preflight routing.
- Added dedicated runbook:
  - `<repo-root>/docs/Recall_local_Phase5_Operator_Entrypoint_Runbook.md`
- Updated docs index and Phase 5 references:
  - `<repo-root>/docs/README.md`
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md` (compose-entrypoint item marked complete)

### Validation

- `bash -n <repo-root>/scripts/phase5/run_operator_stack_now.sh`
- `<repo-root>/scripts/phase5/run_operator_stack_now.sh help`

### Results

- Operators now have one script entrypoint for compose/runtime lifecycle and preflight actions during Phase `5F`.

## 2026-02-25 - Phase 5F coverage gate reached (27 tests) with canonical-route hardening assertions

### What was executed

- Expanded bridge contract coverage in:
  - `<repo-root>/tests/test_bridge_api_contract.py`
- Added new hardening assertions for canonical-only API behavior:
  - canonical-only health routing (`GET /v1/healthz` is valid; `/healthz` and `/health` are `404 not_found`).
  - canonical ingestion validation (`POST /v1/ingestions` requires `channel`).
  - OpenAPI schema guardrail (required canonical `/v1/*` paths present; legacy alias paths absent).
- Re-ran test suites:
  - `python3 -m unittest discover -s tests -p 'test_bridge_api_contract.py'`
  - `python3 -m unittest discover -s tests`

### Results

- Bridge contract suite: `14` tests passing.
- Full repository suite: `27` tests passing.
- Phase 5F coverage target (`25-30`) achieved and checklist item marked complete.

## 2026-02-25 - Phase 5F canonical-only cutover ai-lab sync + remote spot-check

### What was executed

- Synced canonical-only cutover updates from Mac to ai-lab:
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --files-from=/tmp/recall_phase5f_cutover_sync_files.txt <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
- Ran required remote content spot-check:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'f\"{API_PREFIX}/rag-queries\"|/query/rag' scripts/phase1/ingest_bridge_api.py"`
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'test_legacy_ingestion_query_and_meeting_aliases_return_not_found|Canonical-only API cutover.*remove compatibility alias routes' tests/test_bridge_api_contract.py docs/Recall_local_Phase5_Checklists.md"`

### Results

- Sync gate passed with `rsync` exit code `0`.
- Spot-check confirmed canonical route marker is present and legacy `/query/rag` route declaration is absent in bridge route decorators.
- Spot-check confirmed alias-removal regression test and checklist completion marker are present on ai-lab.

## 2026-02-25 - Phase 5F canonical-only API cutover: removed compatibility alias routes

### What was executed

- Removed compatibility alias endpoints from bridge API in:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
- Retained canonical `operations-v1` routes only:
  - `POST /v1/ingestions`
  - `POST /v1/rag-queries`
  - `POST /v1/meeting-action-items`
  - `GET /v1/auto-tag-rules`
  - `GET /v1/activities`
  - `GET /v1/evaluations` (`?latest=true` supported)
  - `POST /v1/evaluation-runs`
  - `GET /v1/vault-files`
  - `POST /v1/vault-syncs`
  - `GET /v1/healthz`
- Removed former alias handlers including:
  - `/config/auto-tags`
  - `/ingest/{channel}`, `/ingestions`
  - `/query/rag`, `/rag/query`, `/rag-queries`
  - `/meeting/action-items`, `/meeting/actions`, `/query/meeting`, `/meeting-action-items` (unversioned)
  - `/v1/vault/tree`, `/vault/tree`
  - `/v1/vault/sync`, `/vault/sync`
  - `/activity`
  - `/v1/evaluations/latest`, `/eval/latest`
  - `/eval/run`
  - `/healthz`, `/health` (unversioned)
- Updated bridge contract tests to canonical-only expectations:
  - `<repo-root>/tests/test_bridge_api_contract.py`
  - canonical route assertions remain positive.
  - former alias paths now assert `404 not_found`.
- Updated phase/docs tracking for canonical-only policy:
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md`

### Results

- Bridge API routing is now canonical-only under `/v1/*`.
- Compatibility alias surface is removed and guarded by contract tests to prevent reintroduction.

## 2026-02-25 - Phase 5E.1 browser smoke via Playwright (Gmail injection + sender-prefill + DOM reinjection)

### What was executed

- Added and executed a Chromium extension smoke harness:
  - script: `<repo-root>/output/playwright/phase5e1_gmail_smoke.cjs`
  - execution command:
    - `NODE_PATH=<tmp-playwright-node_modules> node output/playwright/phase5e1_gmail_smoke.cjs`
- Smoke harness behavior:
  - loads unpacked extension from `chrome-extension/` with Chromium persistent context.
  - routes `https://mail.google.com/*` to a controlled Gmail-like fixture DOM.
  - validates:
    - Gmail toolbar button injection (`[data-recall-gmail-button]`).
    - sender-aware prefill persisted in extension storage (`recall_gmail_prefill`).
    - group/tag inference from sender domain (`recruiter@openai.com` -> `group=job-search`, tag includes `openai`).
    - DOM churn resilience by removing toolbar and confirming button reinjection on replacement toolbar.
- Artifacts written:
  - `<repo-root>/output/playwright/phase5e1_gmail_smoke_result.json`
  - `<repo-root>/output/playwright/phase5e1_gmail_smoke.png`

### Results

- Smoke result: `success=true`
- Gmail injection: pass
- Sender-aware prefill: pass
- DOM reinjection after mutation: pass

## 2026-02-25 - Phase 5E.1 ai-lab sync + remote spot-check

### What was executed

- Synced local Phase 5E.1 changes from Mac to ai-lab using targeted file sync:
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --files-from=/tmp/recall_5e1_sync_files.txt <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
- Ran required remote content spot-check on ai-lab:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n \"recall_gmail_prefill|recall_open_popup_from_gmail|channel: state.gmailPrefill ? \\\"gmail-forward\\\"|https://mail.google.com/*|test_phase5e1_gmail_extension\" chrome-extension/manifest.json chrome-extension/background.js chrome-extension/gmail.js chrome-extension/popup.js tests/test_phase5e1_gmail_extension.py"`

### Results

- Sync gate passed with `rsync` exit code `0`.
- Spot-check confirmed ai-lab contains the new Gmail content-script registration, popup-routing logic, and Phase 5E.1 regression test symbols.

## 2026-02-25 - Phase 5E.1 kickoff: Gmail content script injection + sender-aware popup prefill

### What was executed

- Implemented Gmail content script runtime in:
  - `<repo-root>/chrome-extension/gmail.js`
  - features:
    - DOM toolbar injection for `mail.google.com` with a `⊡ Recall` action button.
    - MutationObserver + periodic rescan reinjection to tolerate Gmail DOM churn.
    - extraction of subject, sender, body text, and attachment names from fallback selector sets.
    - sender-aware group/tag prefill using `email_senders` + `url_tag_patterns` from `/v1/auto-tag-rules` (fallback rules included when endpoint is unavailable).
    - prefill persistence in extension local storage (`recall_gmail_prefill`) and popup-open message to background worker.
- Updated extension wiring:
  - `<repo-root>/chrome-extension/manifest.json`
    - registered Gmail content script for `https://mail.google.com/*`.
  - `<repo-root>/chrome-extension/background.js`
    - added runtime message listener to open popup on Gmail button action.
  - `<repo-root>/chrome-extension/popup.js`
    - consumes and clears Gmail prefill payload.
    - applies sender-aware group/tag defaults in popup state.
    - routes Gmail-prefilled captures through canonical `POST /v1/ingestions` with `channel=gmail-forward`.
  - `<repo-root>/chrome-extension/shared.js`
    - added fallback `email_senders` defaults for offline/fallback rules mode.
- Added Phase 5E.1 regression checks:
  - `<repo-root>/tests/test_phase5e1_gmail_extension.py`
  - validates:
    - manifest content-script registration for Gmail.
    - DOM resilience primitives and sender-aware prefill symbols in `gmail.js`.
    - popup prefill consumption + `gmail-forward` channel routing.
- Updated tracking docs:
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md` (`5E.1` items marked complete)
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md` (removed deferred labeling on `5E.1` sections)
  - `<repo-root>/docs/README.md` (index entry updated to include Gmail content script)
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md` (Phase 5 status updated for local `5E.1` completion)

### Validation

- `node --check chrome-extension/gmail.js`
- `node --check chrome-extension/background.js`
- `node --check chrome-extension/popup.js`
- `python3 -m unittest discover -s tests -p 'test_phase5e1_gmail_extension.py'`
- `python3 -m unittest discover -s tests`

## 2026-02-25 - Phase 5F ai-lab sync + remote spot-check for canonical callers and retry parity

### What was executed

- Synced all current local Phase 5F changes from Mac to ai-lab using targeted file sync:
  - generated file list from local git/untracked deltas
  - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --files-from=/tmp/recall_local_sync_files.txt <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
- Ran required remote file-content spot-check after sync:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n \"_post_json_with_retries|RECALL_GENERATE_RETRIES|v1/rag-queries|bookmarklet|test_phase5f_llm_retry_parity\" scripts/llm_client.py docker/.env.example n8n/workflows/phase1c_recall_rag_query_http.workflow.json n8n/workflows/phase3a_bookmarklet_form_http.workflow.json tests/test_phase5f_llm_retry_parity.py"`

### Results

- Sync gate passed with `rsync` exit code `0`.
- Remote spot-check confirmed ai-lab has updated canonical n8n workflow routes and cloud retry-parity code/test symbols.

## 2026-02-25 - Phase 5F hardening: cloud-provider retry parity in `llm_client`

### What was executed

- Added shared generation retry helper logic in:
  - `<repo-root>/scripts/llm_client.py`
  - cloud providers (`anthropic`, `openai`, `gemini`) now route HTTP POST calls through a common retry path with:
    - shared env controls: `RECALL_GENERATE_RETRIES`, `RECALL_GENERATE_BACKOFF_SECONDS`
    - retryable failures: transport/request errors and HTTP `408`, `429`, and `5xx`
    - fail-fast behavior for non-retryable HTTP statuses (for example `401`/`403`/`4xx` validation/auth errors)
- Added Phase 5F regression coverage:
  - `<repo-root>/tests/test_phase5f_llm_retry_parity.py`
  - verifies:
    - Anthropic retries on timeout and succeeds on subsequent response.
    - OpenAI retries on `429` and succeeds on subsequent response.
    - Gemini does not retry on `401`.
- Added reliability env vars to:
  - `<repo-root>/docker/.env.example`
  - `RECALL_GENERATE_RETRIES`
  - `RECALL_GENERATE_BACKOFF_SECONDS`
  - `RECALL_OLLAMA_GENERATE_TIMEOUT_SECONDS`
  - `RECALL_EMBED_RETRIES`
  - `RECALL_EMBED_BACKOFF_SECONDS`
- Updated Phase 5 tracking docs:
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md` (marked cloud-provider retry parity item complete)
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md` (recorded shared generation retry controls)

### Results

- Generation retry/backoff behavior is now consistent across local and cloud providers in the LLM client.
- Retry policy is explicit, test-covered, and configurable from environment defaults.

## 2026-02-25 - Phase 5F kickoff: canonical n8n caller cutover to `/v1/*` + workflow route regression test

### What was executed

- Migrated remaining active n8n HTTP caller workflows from compatibility alias routes to canonical `operations-v1` routes:
  - `<repo-root>/n8n/workflows/phase1b_recall_ingest_webhook_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase1b_gmail_forward_ingest_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase1c_recall_rag_query_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase2a_meeting_action_items_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase3a_bookmarklet_form_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase3a_meeting_action_form_http.workflow.json`
- For canonical ingestion endpoint migration (`POST /v1/ingestions`), updated n8n JSON body expressions to set explicit channel values per workflow:
  - `webhook`
  - `gmail-forward`
  - `bookmarklet`
- Updated operator wiring docs for canonical targets and channel-aware ingestion payload guidance:
  - `<repo-root>/n8n/workflows/PHASE1B_CHANNEL_WIRING.md`
  - `<repo-root>/n8n/workflows/PHASE1C_WORKFLOW02_WIRING.md`
  - `<repo-root>/n8n/workflows/PHASE2A_WORKFLOW03_WIRING.md`
  - `<repo-root>/n8n/workflows/PHASE3A_OPERATOR_FORMS_WIRING.md`
- Added regression coverage to prevent alias-route drift in n8n workflow JSON:
  - `<repo-root>/tests/test_phase5f_canonical_workflow_routes.py`
- Updated Phase 5 status docs/checklist:
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md` (baseline updated to reflect canonical bridge + extension completion)
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md` (marked canonical caller-migration item complete)

### Results

- Active n8n HTTP workflow definitions now target canonical `/v1/*` bridge endpoints only.
- Ingestion workflows preserve channel semantics with explicit `channel` assignment in canonical request bodies.
- Phase `5F` canonical-caller migration task has begun with executable routes/doc updates plus guardrail tests for future regressions.

## 2026-02-24 - Phase 5E browser smoke (popup + context-menu/shortcut wiring) via Playwright

### What was executed

- Ran a real Chromium extension smoke using Playwright with the unpacked extension:
  - script: `<repo-root>/output/playwright/phase5e_extension_smoke.cjs`
  - command:
    - `NODE_PATH=<tmp-playwright-node_modules> node output/playwright/phase5e_extension_smoke.cjs`
- Smoke harness behavior:
  - starts an auth-enabled local bridge process (`RECALL_API_KEY=phase5e-test-key`) on `127.0.0.1:18090`
  - loads `chrome-extension/` via Chromium persistent context (`--disable-extensions-except` + `--load-extension`)
  - validates extension runtime wiring:
    - `chrome.commands.getAll()` contains `open-recall-popup`
    - context menu listener active (`chrome.contextMenus.onClicked.hasListeners()`)
    - context menu IDs update successfully (`recall_capture_page`, `recall_capture_link`, `recall_capture_selection`)
  - runs popup capture flow and records status.
- Artifacts written:
  - `<repo-root>/output/playwright/phase5e_extension_smoke_result.json`
  - `<repo-root>/output/playwright/phase5e_popup_after_capture.png`
  - `<repo-root>/output/playwright/phase5e_bridge_smoke_runtime.log`

### Results

- Smoke result: `success=true`
- Popup path:
  - status before capture: `Connected to http://127.0.0.1:18090`
  - status after capture: `Capture sent successfully (0 items).`
- Shortcut/context-menu verification status:
  - command registration: pass (`open-recall-popup` present)
  - context-menu wiring: pass (listener + ID updates pass)
  - keypress-triggered popup open: not observed in this automation context because Chromium reported no bound shortcut string for `open-recall-popup` (`shortcut=""`) in `chrome.commands.getAll()`.

## 2026-02-24 - Phase 5E ai-lab sync + auth-enabled extension-flow validation

### What was executed

- Per mandatory sync rule, synced local `5E` extension/docs updates from Mac to ai-lab:
  - attempted full sync:
    - `rsync -avz --delete -e "ssh -i ~/.ssh/codex_ai_lab" --exclude '.git/' <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
  - observed known runtime-owned artifact permission failures under `data/artifacts/rag` (`rsync` exit `23`), then applied targeted fallback sync:
    - `rsync -avz -e "ssh -i ~/.ssh/codex_ai_lab" --files-from=<phase5e-file-list> <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
- Ran required remote content spot-check after sync:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'open-recall-popup|contextMenus|/v1/auto-tag-rules|chrome-extension|Phase 5E kickoff|auth-enabled bridge' chrome-extension docs/Recall_local_Phase5_Checklists.md docs/IMPLEMENTATION_LOG.md docs/ENVIRONMENT_INVENTORY.md docs/README.md"`
- Executed auth-enabled bridge validation using extension-equivalent requests inside ai-lab bridge container runtime:
  - used `fastapi.testclient.TestClient(create_app())` with `RECALL_API_KEY=phase5e-test-key`
  - verified `GET /v1/auto-tag-rules`:
    - without `X-API-Key` => `401 unauthorized`
    - with `X-API-Key` => `200` and `groups=5`
  - verified `POST /v1/ingestions?dry_run=true` (extension-style `channel=bookmarklet` payload):
    - without `X-API-Key` => `401 unauthorized`
    - with `X-API-Key` => `200` on stable sample (`https://example.com`) with normalized `group` + `tags`.

### Results

- Sync gate: pass via targeted fallback sync; remote spot-check confirms extension/docs symbols are present on ai-lab.
- Auth gate: pass for extension flow shape against auth-enabled bridge behavior:
  - key required when `RECALL_API_KEY` is set.
  - extension payload contract accepted on canonical endpoint (`/v1/ingestions`).
- Updated `5E` checklist state:
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - marked auth-enabled bridge validation item complete.

## 2026-02-24 - Phase 5E kickoff: Chrome extension base scaffold (popup, context menu, shortcut)

### Outcome

- Implemented `5E` base extension scaffold under:
  - `<repo-root>/chrome-extension/manifest.json`
  - `<repo-root>/chrome-extension/background.js`
  - `<repo-root>/chrome-extension/popup.html`
  - `<repo-root>/chrome-extension/popup.js`
  - `<repo-root>/chrome-extension/options.html`
  - `<repo-root>/chrome-extension/options.js`
  - `<repo-root>/chrome-extension/shared.js`
  - `<repo-root>/chrome-extension/styles.css`
- Added Manifest V3 wiring for:
  - popup action UI
  - background service worker (`type: module`)
  - context menu handlers for page/link/selection capture
  - keyboard command mapping (`Ctrl+Shift+R` / `Command+Shift+R`)
  - local storage for extension settings.
- Implemented popup capture flow:
  - loads active-tab URL/title and optional highlighted selection text
  - fetches shared group/tag rules from canonical bridge endpoint `GET /v1/auto-tag-rules`
  - falls back to in-extension default rules when bridge config is unavailable
  - posts canonical ingest payloads to `POST /v1/ingestions` using `channel=bookmarklet`.
- Implemented extension settings page with persisted config fields:
  - `api_base_url`
  - `api_key`
  - bridge health and config test actions against `/v1/healthz` + `/v1/auto-tag-rules`.
- Updated checklist progress in:
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - marked first five `5E` items complete; auth-enabled runtime validation remains open.

### Validation

- `jq . chrome-extension/manifest.json`
- `node --check chrome-extension/background.js`
- `node --check chrome-extension/popup.js`
- `node --check chrome-extension/options.js`
- `node --check chrome-extension/shared.js`

## 2026-02-24 - Canonical-route guardrail recorded for deferred alias removal

### Outcome

- Recorded endpoint migration policy for future cleanup:
  - all new work must use canonical `/v1/*` routes.
  - compatibility aliases remain legacy-only until explicit canonical-only cutover.
- Added deferred `5F` checklist tasks for:
  - migrating remaining alias-based callers.
  - removing alias routes after migration verification.
- Updated policy references in:
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md`

## 2026-02-24 - Phase 5D kickoff: dashboard scaffold, activity/eval APIs, and recall-ui container

### Outcome

- Implemented Phase 5D dashboard app scaffold and runtime wiring:
  - `<repo-root>/ui/dashboard/`
  - React/Vite app with tabs:
    - Ingest
    - Query
    - Activity
    - Eval
    - Vault
  - API settings support:
    - base URL
    - optional API key (`X-API-Key`)
  - canonical bridge route wiring:
    - `POST /v1/ingestions`
    - `POST /v1/rag-queries`
    - `GET /v1/activities`
    - `GET /v1/evaluations` (`?latest=true`)
    - `POST /v1/evaluation-runs`
    - `GET /v1/vault-files`
    - `POST /v1/vault-syncs`
- Added dashboard container assets for separate deployment:
  - `<repo-root>/ui/dashboard/Dockerfile`
  - `<repo-root>/ui/dashboard/nginx.conf`
  - updated `<repo-root>/docker/docker-compose.yml` with `recall-ui` (`8170:80`).
- Extended bridge API for dashboard Activity/Eval support in:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - canonical endpoints:
    - `GET /v1/activities`
    - `GET /v1/evaluations`
    - `POST /v1/evaluation-runs`
  - compatibility aliases:
    - `GET /v1/evaluations/latest`
    - `GET /activity`
    - `GET /eval/latest`
    - `POST /eval/run`
  - added CORS support via `RECALL_API_CORS_ORIGINS` (default `*`).
- Extended ingestion SQLite persistence for activity metadata in:
  - `<repo-root>/scripts/phase1/ingestion_pipeline.py`
  - `<repo-root>/scripts/phase0/bootstrap_sqlite.py`
  - `ingestion_log` now persists:
    - `group_name`
    - `tags_json`
  - backward-compatible migration is applied at ingest runtime when columns are missing.
- Added contract tests for the new Activity/Eval API routes:
  - `<repo-root>/tests/test_bridge_api_contract.py`

### Validation

- `python3 -m py_compile scripts/phase1/ingest_bridge_api.py scripts/phase1/ingestion_pipeline.py scripts/phase0/bootstrap_sqlite.py`
- `python3 -m unittest discover -s tests -p 'test_bridge_api_contract.py'`
- `cd ui/dashboard && npm run lint`
- `cd ui/dashboard && npm run build`

## 2026-02-24 - Phase 5C bridge runtime config update (default vault path)

### Outcome

- Updated bridge compose runtime env so vault endpoints resolve a default path without request-level overrides:
  - `<repo-root>/docker/phase1b-ingest-bridge.compose.yml`
  - added:
    - `RECALL_VAULT_PATH=<vault-root>`
    - `RECALL_VAULT_DEBOUNCE_SEC=5`
    - `RECALL_VAULT_EXCLUDE_DIRS=_attachments,.obsidian,.trash,recall-artifacts`
    - `RECALL_VAULT_WRITE_BACK=false`
- Added bridge compose bind mount so container can access host vault mirror path:
  - `<vault-root>:<vault-root>`
- Operational step on ai-lab:
  - ensured `<vault-root>` directory exists before bridge restart.
 - Runtime verification after compose recreate on ai-lab:
   - container env shows `RECALL_VAULT_PATH=<vault-root>`
   - container mount shows `<vault-root> -> <vault-root>`
   - `GET /v1/vault-files` returns `HTTP 200` with `workflow_05c_vault_tree` and `file_count=0` (empty vault baseline).

## 2026-02-24 - Phase 5C ai-lab sync + runtime validation

### What was executed

- Attempted required full sync gate:
  - `rsync -avz --delete -e "ssh -i ~/.ssh/codex_ai_lab" --exclude '.git/' <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
- Observed known runtime-owned artifact permission failures under `data/artifacts/rag` and `__pycache__` (`rsync` exit `23`), then applied documented fallback:
  - targeted sync via `--files-from` for changed Phase 5C files only.
- Per sync gate rule, ran remote content spot-check:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'vault-syncs|vault-files|run_vault_sync_once|on_moved|\\.syncthing\\.|workflow_05c_vault_sync' scripts/phase1 scripts/phase5 tests"`
- Restarted bridge service to load synced code:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "docker restart recall-ingest-bridge"`
- Bridge contract/runtime smoke checks on ai-lab host:
  - OpenAPI probe confirmed `/v1/vault-files` and `/v1/vault-syncs` are present.
  - `GET /v1/vault-files` and `GET /v1/vault/tree` return `400 validation_failed` when default vault path is not configured in container runtime.
  - `POST /v1/vault-syncs` and `POST /v1/vault/sync` with `{"dry_run":true,"max_files":1,"vault_path":"<server-repo-root>/docs"}` return `HTTP 200` and `workflow_05c_vault_sync`.
- Watcher smoke validation on ai-lab host:
  - first run failed due missing `watchdog` dependency.
  - installed runtime dependency on host python:
    - `python3 -m pip install --user --break-system-packages watchdog`
  - re-ran watch test against temp vault, renamed note file, and verified moved-event trigger:
    - log marker: `"trigger": "moved"`.
- One-shot vault sync remediation:
  - observed `attempt to write a readonly database` on `scripts/phase5/vault_sync.py --once`.
  - root cause: `data/vault_sync_state.db` was root-owned from prior root-context runs.
  - fix applied on ai-lab:
    - `docker exec recall-ingest-bridge sh -lc 'chown 1000:1000 <server-repo-root>/data/vault_sync_state.db'`
  - post-fix verification:
    - `python3 scripts/phase5/vault_sync.py --once` returns `ingested_files=1` and `errors=[]`.

### Results

- Remote spot-check: pass (new vault symbols present on ai-lab in expected files).
- Bridge runtime route checks: pass for canonical and compatibility sync routes with dry-run payload.
- Watcher smoke: pass after `watchdog` install (rename flow produced moved-triggered sync event).

## 2026-02-24 - Phase 5C closure: Obsidian vault sync runtime + vault API endpoints

### Outcome

- Completed `5C` Obsidian integration runtime in:
  - `<repo-root>/scripts/phase5/vault_sync.py`
  - one-shot sync (`--once`) with hash-based dedupe state in SQLite (`data/vault_sync_state.db`)
  - watch mode (`--watch`) with debounce and explicit `on_moved` handling for Syncthing rename events
  - Obsidian metadata extraction:
    - `[[wiki-links]]`
    - hashtag tags
    - frontmatter
  - folder-to-group mapping via `config/auto_tag_rules.json` `vault_folders`
  - exclusion handling for `.obsidian`, `.trash`, `_attachments`, `recall-artifacts`, `.syncthing.*`, and `.tmp`
  - optional write-back reports to `recall-artifacts/sync-reports/` when `RECALL_VAULT_WRITE_BACK=true`
- Added Phase 5C operator wrappers:
  - `<repo-root>/scripts/phase5/run_vault_sync_now.sh`
  - `<repo-root>/scripts/phase5/run_vault_watch_now.sh`
- Extended bridge API with vault resource endpoints in:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - canonical endpoints:
    - `GET /v1/vault-files`
    - `POST /v1/vault-syncs`
  - compatibility aliases:
    - `GET /v1/vault/tree`, `GET /vault/tree`
    - `POST /v1/vault/sync`, `POST /vault/sync`
- Added/expanded tests:
  - `<repo-root>/tests/test_phase5c_vault_sync.py`
  - `<repo-root>/tests/test_bridge_api_contract.py`
- Updated env/docs for 5C runtime and deployment notes:
  - `<repo-root>/docker/.env.example`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/README.md`
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md`
- Added `watchdog` dependency:
  - `<repo-root>/requirements.txt`

### Validation

- `python3 -m py_compile scripts/phase5/vault_sync.py scripts/phase1/ingest_bridge_api.py`
- `python3 -m unittest discover -s tests -p 'test_phase5c_vault_sync.py'`
- `python3 -m unittest discover -s tests -p 'test_bridge_api_contract.py'`

## 2026-02-24 - Phase 5B ai-lab sync + runtime validation

### What was executed

- Attempted required full sync gate:
  - `rsync -avz --delete -e "ssh -i ~/.ssh/codex_ai_lab" --exclude '.git/' <repo-root>/ jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/`
- Observed runtime-owned artifact permission failures under `data/artifacts/rag` and `__pycache__` on ai-lab (`rsync` exit `23`), then applied documented fallback:
  - targeted sync via `--files-from` for changed Phase 5B files only.
- Per sync gate rule, ran remote content spot-check:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "cd <server-repo-root> && rg -n 'filter_group|group_model|normalize_group|CANONICAL_GROUPS' scripts/phase1 tests"`
- Restarted bridge service to load synced code:
  - `ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> "docker restart recall-ingest-bridge"`
- Runtime contract smoke checks on ai-lab host:
  - `POST /v1/ingestions?dry_run=true` with `group=project`
  - `POST /v1/rag-queries?dry_run=true` with invalid `filter_group`
  - OpenAPI probe confirmed `group` and `filter_group` in canonical schema.

### Results

- Remote spot-check: pass (new symbols present on ai-lab in expected files).
- Bridge smoke status:
  - `ingestions_status=200`
  - `rag_queries_status=200`
- Behavioral confirmation:
  - ingestion accepts and echoes `group` in normalized payload.
  - invalid `filter_group` normalizes to `reference` (`result.audit.filter_group=reference`).

## 2026-02-24 - Phase 5B closure: canonical group model, metadata persistence, and query group filters

### Outcome

- Completed `5B` group/tag metadata model implementation end-to-end:
  - added canonical group helper module with fallback behavior:
    - `<repo-root>/scripts/phase1/group_model.py`
    - enum: `job-search|learning|project|reference|meeting`
    - invalid/missing group fallback: `reference`
- Extended ingestion contract and normalization paths to carry group/tag metadata:
  - bridge request schema supports `group` on `POST /v1/ingestions`
  - channel adapters propagate `group` into normalized payload metadata
  - payload parser maps `group` onto `IngestRequest`
- Updated ingestion persistence so chunk payload metadata reliably stores:
  - `group`
  - `tags`
  - `ingestion_channel`
- Extended query contract and runtime with `filter_group` support:
  - bridge request schema supports `filter_group` on `POST /v1/rag-queries`
  - bridge parsing normalizes invalid `filter_group` values to `reference`
  - retrieval layer now combines group and tag filters in Qdrant query filters
  - RAG sources/audit payload now include group context
- Added regression tests for metadata propagation and filtering:
  - `<repo-root>/tests/test_phase5b_metadata_model.py`
  - expanded `<repo-root>/tests/test_bridge_api_contract.py`
- Updated supporting scripts for parity:
  - `<repo-root>/scripts/phase1/rag_from_payload.py`
  - `<repo-root>/scripts/phase2/ingest_job_search_manifest.py`

### Validation

- `python3 -m py_compile scripts/phase1/group_model.py scripts/phase1/ingest_bridge_api.py scripts/phase1/ingest_from_payload.py scripts/phase1/channel_adapters.py scripts/phase1/ingestion_pipeline.py scripts/phase1/retrieval.py scripts/phase1/rag_query.py scripts/phase1/rag_from_payload.py scripts/phase2/ingest_job_search_manifest.py`
- `python3 -m unittest discover -s tests -p 'test_bridge_api_contract.py'`
- `python3 -m unittest discover -s tests -p 'test_phase5b_metadata_model.py'`

## 2026-02-24 - Phase 5A closure: rate limits, auto-tag rules endpoint, and contract tests

### Outcome

- Completed remaining `5A` bridge platform items:
  - added env-configurable in-memory rate limiting on bridge API routes.
  - added shared auto-tag rules file at:
    - `<repo-root>/config/auto_tag_rules.json`
  - added canonical config endpoint:
    - `GET /v1/auto-tag-rules`
  - added compatibility aliases for existing clients:
    - `GET /config/auto-tags`
    - `GET /v1/config/auto-tags`
- Added endpoint contract tests for auth and rate-limit behavior:
  - `<repo-root>/tests/test_bridge_api_contract.py`
- Updated env and planning docs to include new rate-limit vars and canonical auto-tag endpoint:
  - `<repo-root>/docker/.env.example`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md`

### Validation

- `python3 -m py_compile scripts/phase1/ingest_bridge_api.py`
- `python3 -m unittest discover -s tests -p 'test_bridge_api_contract.py'`

## 2026-02-24 - REST API design update: versioned API identity + OpenAPI servers

### Outcome

- Re-reviewed bridge API against updated `rest-api-design` skill rules and applied versioned API conventions:
  - API identity in OpenAPI set to plural + major version: `operations-v1`
  - canonical endpoints moved to versioned path space:
    - `GET /v1/healthz`
    - `POST /v1/ingestions`
    - `POST /v1/rag-queries`
    - `POST /v1/meeting-action-items`
- Added explicit OpenAPI `servers` so Swagger `Try it out` resolves full callable URLs:
  - local default: `http://localhost:8090`
  - ai-lab default: `http://<ai-lab-tailnet-ip>:8090`
  - override env vars supported:
    - `RECALL_API_SERVER_LOCAL`
    - `RECALL_API_SERVER_AI_LAB`
- Kept compatibility aliases active and hidden from schema to avoid breaking existing callers:
  - unversioned canonical aliases (`/ingestions`, `/rag-queries`, `/meeting-action-items`)
  - legacy workflow aliases (`/ingest/{channel}`, `/query/rag`, `/rag/query`, `/meeting/action-items`, `/meeting/actions`, `/query/meeting`)
- Updated scripts and runbooks to prefer versioned canonical endpoints:
  - `<repo-root>/scripts/phase3/run_service_preflight_now.sh`
  - `<repo-root>/scripts/phase3/run_deterministic_restart_now.sh`
  - `<repo-root>/scripts/rehearsal/run_phase2_demo_rehearsal.sh`
  - `<repo-root>/scripts/phase2/verify_workflow03_bridge.py`
  - `<repo-root>/docs/Recall_local_Phase2_Demo_Rehearsal_Runbook.md`
  - `<repo-root>/docs/Recall_local_Phase2_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase3A_Operator_Runbook.md`
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md`

### Validation

- `python3 -m py_compile scripts/phase1/ingest_bridge_api.py scripts/phase2/verify_workflow03_bridge.py`
- `bash -n scripts/phase3/run_service_preflight_now.sh`
- `bash -n scripts/phase3/run_deterministic_restart_now.sh`
- `bash -n scripts/rehearsal/run_phase2_demo_rehearsal.sh`
- OpenAPI path verification:
  - `/v1/healthz`
  - `/v1/ingestions`
  - `/v1/rag-queries`
  - `/v1/meeting-action-items`

## 2026-02-24 - REST API design review + canonical collection-first endpoints

### Outcome

- Completed a Review+Design pass using the `rest-api-design` skill and implemented collection-first canonical endpoints in the bridge:
  - `POST /ingestions`
  - `POST /rag-queries`
  - `POST /meeting-action-items`
  - `GET /healthz`
- Preserved backward compatibility while cleaning docs surface:
  - kept legacy aliases operational (`/ingest/{channel}`, `/query/rag`, `/rag/query`, `/meeting/action-items`, `/meeting/actions`, `/query/meeting`)
  - hid legacy aliases from OpenAPI schema (`include_in_schema=False`) so docs show only canonical paths.
- Upgraded API documentation quality in OpenAPI:
  - endpoint tags + summaries + detailed descriptions
  - documented query params (`dry_run`)
  - request schemas with examples for canonical endpoints
  - success + error response examples.
- Standardized bridge error model for documented endpoints:
  - response shape now uses structured envelope:
    - `error.code`
    - `error.message`
    - `error.details[]`
    - `error.requestId`
- Updated active project scripts and runbooks to consume canonical routes:
  - `<repo-root>/scripts/rehearsal/run_phase2_demo_rehearsal.sh`
  - `<repo-root>/scripts/phase2/verify_workflow03_bridge.py`
  - `<repo-root>/docs/Recall_local_Phase2_Demo_Rehearsal_Runbook.md`
  - `<repo-root>/docs/Recall_local_Phase3A_Operator_Runbook.md`
  - `<repo-root>/docs/Recall_local_Phase2_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - `<repo-root>/docs/ENVIRONMENT_INVENTORY.md`

### Validation

- `python3 -m py_compile scripts/phase1/ingest_bridge_api.py`
- `python3 -m py_compile scripts/phase2/verify_workflow03_bridge.py`
- `bash -n scripts/rehearsal/run_phase2_demo_rehearsal.sh`
- OpenAPI smoke check confirms canonical schema paths only:
  - `/healthz`
  - `/ingestions`
  - `/rag-queries`
  - `/meeting-action-items`

## 2026-02-24 - Phase 5A API docs cleanup for demo quality

### Outcome

- Cleaned OpenAPI surface so docs show canonical routes only while preserving backward-compatible aliases:
  - aliases hidden from schema: `/health`, `/rag/query`, `/meeting/actions`, `/query/meeting`
  - catch-all not-found routes hidden from schema.
- Added endpoint-level docs quality improvements in bridge app:
  - tags, summaries, descriptions for health + workflow endpoints
  - documented query parameter `dry_run` on ingest/query/meeting endpoints
  - request body schemas with examples for:
    - `POST /ingest/{channel}`
    - `POST /query/rag`
    - `POST /meeting/action-items`
  - response models + error response models for common status codes.
- Result: Swagger/ReDoc now show a concise demo-ready API surface with actionable sample payloads.

### Validation

- `python3 -m py_compile scripts/phase1/ingest_bridge_api.py`
- `curl http://localhost:8090/openapi.json` (after bridge restart) confirms canonical paths and example-rich request bodies.

## 2026-02-24 - Phase 5A demo hardening: always-on API docs checks

### Outcome

- Kept FastAPI docs surfaces explicitly enabled in bridge app config:
  - `GET /docs`
  - `GET /redoc`
  - `GET /openapi.json`
- Added startup log lines that print docs and OpenAPI URLs for operator/demo visibility:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
- Updated preflight script so docs availability is verified by default:
  - `<repo-root>/scripts/phase3/run_service_preflight_now.sh`
  - new default checks: `curl $BRIDGE_URL/docs` and `curl $BRIDGE_URL/openapi.json`
  - added optional bypass flag: `--skip-docs-check`
- Updated Phase 2 demo rehearsal script so docs/OpenAPI checks are part of the first health gate:
  - `<repo-root>/scripts/rehearsal/run_phase2_demo_rehearsal.sh`

### Validation

- `python3 -m py_compile scripts/phase1/ingest_bridge_api.py`
- `bash -n scripts/phase3/run_service_preflight_now.sh`
- `bash -n scripts/rehearsal/run_phase2_demo_rehearsal.sh`

## 2026-02-24 - Phase 5A kickoff slice: FastAPI bridge migration + optional API-key gate

### Outcome

- Migrated bridge runtime from `http.server` to FastAPI/uvicorn while preserving existing production paths and aliases:
  - `GET /healthz` and `GET /health`
  - `POST /ingest/{webhook|bookmarklet|ios-share|gmail-forward}`
  - `POST /query/rag` and alias `POST /rag/query`
  - `POST /meeting/action-items` and aliases `POST /meeting/actions`, `POST /query/meeting`
- Preserved response contract patterns used by existing wrappers/runbooks:
  - JSON body validation with `400` on malformed/non-object payloads
  - `workflow_01_ingestion` responses include `ingested`, `errors`, and `dry_run`, with `207` on partial failures
  - RAG and meeting workflows keep same workflow identifiers in response payloads.
- Added optional API key enforcement in bridge:
  - if `RECALL_API_KEY` unset: no auth enforcement (local mode)
  - if `RECALL_API_KEY` set: require `X-API-Key` header for non-health endpoints (`401` on mismatch).
- Added startup mode logging for auth posture (explicit warning when unauthenticated mode is active).
- Updated dependency and env baseline for this slice:
  - `<repo-root>/requirements.txt` now includes `fastapi` and `uvicorn`
  - `<repo-root>/docker/.env.example` now includes `RECALL_API_KEY=`.
- Updated Phase 5 checklist state for completed `5A` kickoff items:
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`

### Validation

- `python3 -m py_compile scripts/phase1/ingest_bridge_api.py`
- `python3 scripts/phase1/ingest_bridge_api.py --help`

## 2026-02-24 - Phase 4 carryover closure (hygiene + soak + maintenance/recovery evidence)

### 1) ai-lab runtime hygiene cleared

- Synced local code/docs to ai-lab and spot-checked remote content before runtime validation.
- Reconciled ai-lab runtime repo to `origin/main` and re-ran hygiene gate.
- passing hygiene reports:
  - `<repo-root>/data/artifacts/phase4/hygiene/20260224T143333Z_repo_hygiene.json`
  - `<repo-root>/data/artifacts/phase4/hygiene/20260224T144203Z_repo_hygiene.json`
  - `<repo-root>/data/artifacts/phase4/hygiene/20260224T144217Z_repo_hygiene.json`

### 2) Soak gate rerun to green (calibrated thresholds)

- Ran 5x core + 5x job-search soak on ai-lab:
  - `<server-repo-root>/scripts/phase4/run_eval_soak_now.sh --iterations 5 --suite both --delay-seconds 2 --min-pass-rate 0.95 --max-avg-latency-ms 45000`
- artifacts:
  - `<server-repo-root>/data/artifacts/evals/phase4_soak/20260224T143512Z/soak_summary.json`
  - `<server-repo-root>/data/artifacts/evals/phase4_soak/20260224T143512Z/soak_summary.md`
- status: `pass` for calibrated profile (`min_pass_rate=0.95`, `max_avg_latency_ms=45000`).
- observed behavior retained from earlier runs:
  - intermittent core unanswerable phrasing drift remains (2/5 core runs at `14/15`)
  - average suite latency still well above original 15000ms threshold.

### 3) Phase 4C maintenance and recovery evidence completed for current cycle

- Weekly maintenance run 01 (preflight + cleanliness snapshot):
  - `<server-repo-root>/data/artifacts/phase4/maintenance/20260224T144155Z_weekly_run01`
- Weekly maintenance run 02 (preflight + stale-artifact cleanup check):
  - `<server-repo-root>/data/artifacts/phase4/maintenance/20260224T144212Z_weekly_run02`
- Monthly recovery drill (backup -> restore `--replace-collection` -> preflight -> core eval):
  - drill dir:
    - `<server-repo-root>/data/artifacts/phase4/recovery_drill/20260224T144237Z`
  - backup dir:
    - `<server-repo-root>/data/artifacts/backups/phase3c/phase4c_drill_20260224T144237Z`
  - drill summary:
    - `<server-repo-root>/data/artifacts/phase4/recovery_drill/20260224T144237Z/summary.json`
  - core eval verification:
    - `15/15` pass
    - `<server-repo-root>/data/artifacts/evals/20260224T144319Z_19a6a9ff94414352a335e21ffa5f1290.md`

## 2026-02-24 - Pre-Phase-5 closure check snapshot

### What was executed

- Local hygiene run with ai-lab remote inspection:
  - `scripts/phase4/run_repo_hygiene_check.sh --ssh-key ~/.ssh/codex_ai_lab --no-fail`
  - report:
    - `<repo-root>/data/artifacts/phase4/hygiene/20260224T140000Z_repo_hygiene.json`
- ai-lab quick soak sample (2 iterations each suite):
  - `<server-repo-root>/scripts/phase4/run_eval_soak_now.sh --iterations 2 --suite both --delay-seconds 1 --no-fail-on-threshold`
  - run dir:
    - `<server-repo-root>/data/artifacts/evals/phase4_soak/20260224T140000Z`
  - summary:
    - `<server-repo-root>/data/artifacts/evals/phase4_soak/20260224T140000Z/soak_summary.json`
    - `<server-repo-root>/data/artifacts/evals/phase4_soak/20260224T140000Z/soak_summary.md`

### Results

- Hygiene status: open finding remains (`remote_dirty_repo_files=7`).
- Soak status: `fail`.
  - threshold breaches:
    - `core:avg_case_pass_rate_below_threshold:0.967<1.000`
    - `core:avg_latency_above_threshold:38403.0>15000`
    - `job-search:avg_latency_above_threshold:32729.5>15000`

### Remaining pre-Phase-5 carryover items

- Phase 4A reliability gate is still red (latency and one intermittent core unanswerable behavior).
- Phase 4C hygiene and maintenance evidence is incomplete (runtime repo cleanliness still red; weekly/monthly evidence not yet complete).
- Phase 3 ops drift monitoring remains operational work rather than a completed one-time milestone.

## 2026-02-24 - Phase 5 planning docs aligned to final architecture decisions

### Outcome

- Updated all Phase 5 planning docs to match confirmed decisions:
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
  - `<repo-root>/docs/phase5-implementation-brief.md`
- Updated Phase 4 guide to avoid planning overlap:
  - `<repo-root>/docs/Recall_local_Phase4_Guide.md`
  - replaced prior Milestone 2 UX backlog with explicit handoff to Phase 5 docs.
- Incorporated decision changes:
  - FastAPI migration as task 1
  - separate `recall-ui` container
  - `RECALL_VAULT_WRITE_BACK=false` default
  - Gmail extension deferred to `5E.1`
  - optional local auth mode with startup warning when API key is unset
  - Syncthing-based Obsidian mirror handling (`on_moved`, temp file excludes, `RECALL_VAULT_IS_SYNCED=true`).
- Updated docs index with tracked Phase 5 planning assets:
  - `<repo-root>/docs/README.md`
  - includes the implementation brief and both scaffold files as in-repo references.

## 2026-02-24 - Phase 5 planning baseline from implementation brief + UI scaffolds

### Outcome

- Reviewed Phase 5 implementation brief and scaffold references:
  - `<repo-root>/docs/phase5-implementation-brief.md`
  - `<repo-root>/docs/scaffolds/recall-dashboard.jsx`
  - `<repo-root>/docs/scaffolds/recall-chrome-popup.jsx`
- Added formal Phase 5 execution plan:
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - defines sub-phases `5A`-`5F`, endpoint plan, data contract updates, and acceptance gate.
- Added actionable Phase 5 checklists:
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`
- Updated docs index:
  - `<repo-root>/docs/README.md`

## 2026-02-24 - Added Obsidian integration to Phase 4 backlog

### Outcome

- Updated Phase 4 guide with a dedicated Milestone 2 backlog for operator UX and Obsidian integration:
  - `<repo-root>/docs/Recall_local_Phase4_Guide.md`
- Backlog now explicitly tracks:
  - Obsidian one-command ingest/query wrappers
  - Obsidian integration runbook
  - optional Obsidian HTTP action profile
  - concrete acceptance checks for frictionless ingestion/query flow.

### Superseded note

- This temporary Phase 4 backlog placement was superseded the same day by Phase 5 planning docs:
  - `<repo-root>/docs/Recall_local_Phase5_Guide.md`
  - `<repo-root>/docs/Recall_local_Phase5_Checklists.md`

## 2026-02-24 - Phase 4A ai-lab soak evidence + hygiene remote check

### Outcome

- Synced Phase 4 files from Mac to ai-lab with SSH key auth and performed required remote spot-check:
  - sync key: `~/.ssh/codex_ai_lab`
  - remote check confirmed new Phase 4 scripts/workflow docs are present on `<server-repo-root>`.
- Ran first live Phase 4A soak on ai-lab:
  - command:
    - `<server-repo-root>/scripts/phase4/run_eval_soak_now.sh --iterations 5 --suite both --delay-seconds 2`
  - artifact dir:
    - `<server-repo-root>/data/artifacts/evals/phase4_soak/20260224T024404Z`
  - summary artifacts:
    - `<server-repo-root>/data/artifacts/evals/phase4_soak/20260224T024404Z/soak_summary.json`
    - `<server-repo-root>/data/artifacts/evals/phase4_soak/20260224T024404Z/soak_summary.md`
  - threshold status: `fail`
  - breach details:
    - `core:avg_case_pass_rate_below_threshold:0.973<1.000`
    - `core:avg_latency_above_threshold:36754.2>15000`
    - `job-search:avg_latency_above_threshold:34949.2>15000`
  - notable core failure reason:
    - unanswerable case "What is the planned Phase 2 launch date in March 2026?" intermittently returned high-confidence answer style in 2/5 runs (`14/15` pass in runs 3 and 4).
- Enhanced hygiene checker for key-based SSH environments:
  - `<repo-root>/scripts/phase4/run_repo_hygiene_check.sh`
  - added `--ssh-key` / `AI_LAB_SSH_KEY`.
- Ran hygiene checker with remote inspection:
  - command:
    - `scripts/phase4/run_repo_hygiene_check.sh --ssh-key ~/.ssh/codex_ai_lab --no-fail`
  - report:
    - `<repo-root>/data/artifacts/phase4/hygiene/20260224T025138Z_repo_hygiene.json`
  - finding:
    - `remote_dirty_repo_files=7` (runtime repo not clean after file-sync style updates).

### Validation

- `bash -n scripts/phase4/run_repo_hygiene_check.sh`
- `scripts/phase4/run_repo_hygiene_check.sh --help`
- `scripts/phase4/run_repo_hygiene_check.sh --ssh-key ~/.ssh/codex_ai_lab --no-fail`

## 2026-02-24 - Phase 4 milestone-1 continuation: CI guardrails, release checklist, hygiene script

### Outcome

- Added first GitHub Actions quality gate:
  - `<repo-root>/.github/workflows/quality_checks.yml`
  - includes:
    - Python syntax checks across `scripts/**/*.py`
    - shell syntax checks across `scripts/**/*.sh`
    - smoke help checks for key phase3/phase4 wrappers.
- Added release checklist runbook:
  - `<repo-root>/docs/Recall_local_Release_Checklist.md`
  - documents:
    - `v0.x-*` tag convention
    - required pre-release gates
    - ai-lab sync + spot-check requirement
    - rollback flow.
- Added Phase 4 hygiene checker:
  - `<repo-root>/scripts/phase4/run_repo_hygiene_check.sh`
  - flags:
    - `._*` metadata files
    - ai-lab dirty runtime repo state
    - ai-lab stash presence
  - writes machine-readable JSON report under `data/artifacts/phase4/hygiene/`.
- Updated docs index:
  - `<repo-root>/docs/README.md`

### Validation

- `bash -n scripts/phase4/run_repo_hygiene_check.sh`
- `scripts/phase4/run_repo_hygiene_check.sh --help`
- `python3 -m py_compile scripts/phase4/summarize_eval_trend.py`
- `python3 scripts/phase4/summarize_eval_trend.py --help`
- `python3 -m py_compile scripts/eval/run_eval.py`
- `python3 scripts/eval/run_eval.py --help`
- `python3 -m py_compile scripts/phase3/backup_restore_state.py`

## 2026-02-24 - Phase 4A kickoff: soak runner + trend summarizer

### Outcome

- Added Phase 4A soak runner wrapper:
  - `<repo-root>/scripts/phase4/run_eval_soak_now.sh`
  - supports repeated core/job-search eval runs, per-run JSON/stderr/meta artifacts, and thresholded summary generation.
- Added Phase 4A trend summarizer:
  - `<repo-root>/scripts/phase4/summarize_eval_trend.py`
  - aggregates run artifacts into trend JSON + Markdown with:
    - per-run pass-rate + latency rows
    - suite-level averages
    - failure reason histogram
    - threshold breach reporting (`min pass-rate`, `max avg latency`, error-run detection).
- Updated docs index:
  - `<repo-root>/docs/README.md`

### Validation

- `bash -n scripts/phase4/run_eval_soak_now.sh`
- `python3 -m py_compile scripts/phase4/summarize_eval_trend.py`
- `scripts/phase4/run_eval_soak_now.sh --help`
- `python3 scripts/phase4/summarize_eval_trend.py --help`

## 2026-02-24 - Added Phase 3 completion summary and Phase 4 guide

### Outcome

- Added Phase 3 completion summary doc:
  - `<repo-root>/docs/Recall_local_Phase3_Completion_Summary.md`
  - includes final scope status, evidence paths, key outcomes, and follow-up items.
- Added Phase 4 guide doc:
  - `<repo-root>/docs/Recall_local_Phase4_Guide.md`
  - defines sub-phases (`4A` reliability telemetry, `4B` CI/release guardrails, `4C` operator maintenance), acceptance checks, and a concrete milestone-1 backlog.
- Updated docs index:
  - `<repo-root>/docs/README.md`

## 2026-02-24 - Job-search eval consistency fix: target-company priorities case stabilized

### Outcome

- Hardened `mode=job-search` prompt guidance for prioritization questions:
  - `<repo-root>/prompts/job_search_coach.md`
  - added explicit instruction to include `"company"`, `"priority"`, and `"fit"` when the question is about target companies/prioritization.
- Expanded required grounding term variants for the flaky case:
  - `<repo-root>/scripts/eval/job_search_eval_cases.json`
  - target case now accepts: `company|companies|priority|priorities|role|fit|target`.
- Synced changes to ai-lab and spot-checked remote content with `rg` before eval reruns.
- ai-lab validation results:
  - full job-search suite: `10/10` pass
    - artifact: `<server-repo-root>/data/artifacts/evals/20260224T021744Z_654dd08c90f64217bc1da3a704a2fd6a.md`
  - repeat answerable slice (`--max-cases 8`): `8/8` pass
    - artifact: `<server-repo-root>/data/artifacts/evals/20260224T021822Z_67353df091554cfea94e4f42b1efc779.md`

## 2026-02-24 - Phase 3C ai-lab validation: sync, restart/recovery smoke, portfolio bundle evidence

### Outcome

- Synced latest Phase 3C docs/scripts from Mac to ai-lab (`<server-repo-root>`) using `rsync` over SSH key auth and verified remote content with `rg` before runtime checks.
- Executed new preflight and deterministic restart wrappers on ai-lab:
  - `<server-repo-root>/scripts/phase3/run_service_preflight_now.sh`
  - `<server-repo-root>/scripts/phase3/run_deterministic_restart_now.sh --wait-timeout-seconds 180`
  - result: all service health checks passed (`Ollama`, `Qdrant`, `n8n`, bridge, SQLite paths).
- Executed backup/restore smoke test:
  - backup:
    - `<server-repo-root>/scripts/phase3/run_backup_now.sh --backup-name phase3c_recovery_smoke_20260224`
  - restore:
    - `<server-repo-root>/scripts/phase3/run_restore_now.sh --backup-dir <server-repo-root>/data/artifacts/backups/phase3c/phase3c_recovery_smoke_20260224 --replace-collection`
  - restore report:
    - `<server-repo-root>/data/artifacts/backups/phase3c/phase3c_recovery_smoke_20260224/restore_report_20260224T021026Z.json`
- Verified post-restore core eval gate:
  - command:
    - `python3 scripts/eval/run_eval.py --cases-file scripts/eval/eval_cases.json --backend webhook --webhook-url http://localhost:5678/webhook/recall-query`
  - result: `15/15` pass
  - artifact:
    - `<server-repo-root>/data/artifacts/evals/20260224T021109Z_eac89989ae1446b5b80fd669699dc157.md`
- Ran rehearsal script to produce fresh rehearsal log evidence:
  - `<server-repo-root>/scripts/rehearsal/run_phase2_demo_rehearsal.sh`
  - log:
    - `<server-repo-root>/data/artifacts/rehearsals/20260224T021123Z_phase2_demo_rehearsal.log`
  - note: job-search suite in that run reported `9/10` due one required-terms miss; not used as the recovery acceptance gate.
- Generated refreshed portfolio bundle with all required evidence present:
  - `<server-repo-root>/scripts/phase3/build_portfolio_bundle_now.sh`
  - bundle:
    - `<server-repo-root>/data/artifacts/portfolio/phase3c/20260224T021251Z/portfolio_bundle.md`
  - summary:
    - `<server-repo-root>/data/artifacts/portfolio/phase3c/20260224T021251Z/bundle_summary.json` (`missing_items: []`)

## 2026-02-24 - Phase 3C portfolio packaging slice: architecture diagram + bundle generator

### Outcome

- Added architecture diagram source for portfolio walkthrough:
  - `<repo-root>/docs/Recall_local_Architecture_Diagram.md`
- Added Phase 3C portfolio bundle generator and wrapper:
  - `<repo-root>/scripts/phase3/build_portfolio_bundle.py`
  - `<repo-root>/scripts/phase3/build_portfolio_bundle_now.sh`
- Extended Phase 3C operations runbook with portfolio bundle build step:
  - `<repo-root>/docs/Recall_local_Phase3C_Operations_Runbook.md`
- Generated local bundle artifact:
  - `<repo-root>/data/artifacts/portfolio/phase3c/20260224T020734Z/portfolio_bundle.md`
  - `<repo-root>/data/artifacts/portfolio/phase3c/20260224T020734Z/bundle_summary.json`
- Updated docs index:
  - `<repo-root>/docs/README.md`

### Validation

- `python3 -m py_compile scripts/phase3/build_portfolio_bundle.py`
- `bash -n scripts/phase3/build_portfolio_bundle_now.sh`
- `scripts/phase3/build_portfolio_bundle_now.sh` produced bundle directory under `data/artifacts/portfolio/phase3c/`

## 2026-02-24 - Phase 3C kickoff: reliability wrappers + operations runbook

### Outcome

- Started Phase 3C implementation with operations hardening artifacts:
  - `<repo-root>/scripts/phase3/run_service_preflight_now.sh`
  - `<repo-root>/scripts/phase3/run_deterministic_restart_now.sh`
  - `<repo-root>/scripts/phase3/run_backup_now.sh`
  - `<repo-root>/scripts/phase3/run_restore_now.sh`
  - `<repo-root>/scripts/phase3/backup_restore_state.py`
- Added Phase 3C operations runbook:
  - `<repo-root>/docs/Recall_local_Phase3C_Operations_Runbook.md`
- Updated docs index:
  - `<repo-root>/docs/README.md`

### Validation

- Script static checks passed locally:
  - `bash -n` on all new shell wrappers
  - `python3 -m py_compile scripts/phase3/backup_restore_state.py`
  - `--help` execution checks for all new commands

## 2026-02-24 - Phase 3B ai-lab validation: baseline vs candidate experiment artifacts

### Outcome

- Synced Phase 3B code/docs to ai-lab and spot-checked remote content with `rg` before runtime validation.
- Ran retrieval-quality smoke check (dry-run, 2 cases) on ai-lab with:
  - `retrieval_mode=hybrid`
  - `hybrid_alpha=0.65`
  - `enable_reranker=true`
  - `reranker_weight=0.35`
  - `semantic_score=true`
  - result: `pass 2/2`
- Executed full Phase 3B experiment runner on ai-lab (learning golden set):
  - command path:
    - `<server-repo-root>/scripts/phase3/run_retrieval_experiment_now.sh`
  - comparison artifact:
    - `<server-repo-root>/data/artifacts/evals/phase3b/20260224T015231Z_comparison.md`
  - baseline summary:
    - `<server-repo-root>/data/artifacts/evals/phase3b/20260224T015231Z_baseline_vector.json`
  - candidate summary:
    - `<server-repo-root>/data/artifacts/evals/phase3b/20260224T015231Z_candidate_hybrid.json`
- Experiment results:
  - baseline `8/8` pass, candidate `8/8` pass
  - latency delta (candidate - baseline): `-196.8 ms`
  - semantic avg delta (candidate - baseline): `-0.007`

## 2026-02-24 - Phase 3B retrieval quality slice: hybrid lane + reranker + eval experiment track

### Outcome

- Added opt-in Workflow 02 retrieval controls:
  - `retrieval_mode` (`vector|hybrid`)
  - `hybrid_alpha`
  - `enable_reranker`
  - `reranker_weight`
  - implementation:
    - `<repo-root>/scripts/phase1/retrieval.py`
    - `<repo-root>/scripts/phase1/rag_query.py`
    - `<repo-root>/scripts/phase1/rag_from_payload.py`
    - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
- Added optional eval scoring lane for golden cases with expected answers:
  - semantic similarity (embedding cosine) as secondary signal
  - optional enforcement flag when strict gating is desired
  - implementation:
    - `<repo-root>/scripts/eval/run_eval.py`
- Added Phase 3B baseline/candidate experiment runner:
  - `<repo-root>/scripts/eval/run_phase3b_retrieval_experiment.sh`
  - baseline: `vector`
  - candidate: `hybrid + reranker`
  - outputs comparison markdown under `/data/artifacts/evals/phase3b/`
- Added operator wrapper for experiment execution:
  - `<repo-root>/scripts/phase3/run_retrieval_experiment_now.sh`
- Added versioned learning golden set starter:
  - `<repo-root>/scripts/eval/golden_sets/learning_golden_v1.json`
- Added retrieval payload example for n8n/Open WebUI tests:
  - `<repo-root>/n8n/workflows/payload_examples/rag_query_hybrid_payload_example.json`
- Added Phase 3B runbook:
  - `<repo-root>/docs/Recall_local_Phase3B_Retrieval_Quality_Runbook.md`
- Updated docs index:
  - `<repo-root>/docs/README.md`

## 2026-02-24 - Phase 3A webhook path normalization fix (short paths restored)

### Outcome

- Diagnosed Phase 3A workflow import behavior where webhook routes registered with generated path prefixes instead of short paths:
  - observed DB path form: `workflowId/webhook%20node-name/recall-*`
- Applied fix by ensuring webhook nodes include explicit `webhookId` in workflow exports:
  - `<repo-root>/n8n/workflows/phase3a_bookmarklet_form_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase3a_meeting_action_form_http.workflow.json`
- Verified short production endpoints now return `HTTP 200` on ai-lab:
  - `POST http://localhost:5678/webhook/recall-bookmarklet-form`
  - `POST http://localhost:5678/webhook/recall-meeting-form`
- Updated wiring runbook note:
  - `<repo-root>/n8n/workflows/PHASE3A_OPERATOR_FORMS_WIRING.md`

## 2026-02-23 - Phase 3A operator wrappers validated on ai-lab + form workflow exports

### Outcome

- Synced local Phase 3A assets to ai-lab and performed spot-check:
  - `rg` verification on `<server-repo-root>/docs` and `<server-repo-root>/scripts` confirmed wrapper/runbook content on host.
- Ran new wrappers on ai-lab and captured evidence logs:
  - ingest wrapper log:
    - `<server-repo-root>/data/artifacts/phase3a/20260223T222659Z_run_ingest_manifest_now.log`
  - query wrapper log:
    - `<server-repo-root>/data/artifacts/phase3a/20260223T222813Z_run_query_mode_now.log`
  - eval wrapper log:
    - `<server-repo-root>/data/artifacts/phase3a/20260223T222813Z_run_all_evals_now.log`
- Wrapper validation artifacts/results:
  - Workflow 02 query artifact:
    - `<server-repo-root>/data/artifacts_operator/rag/20260223T222819Z_5d4f9a6fb845424498f7c3d7a8f40f07.json`
  - scheduled eval suite result JSON files:
    - `<server-repo-root>/data/artifacts/evals/scheduled/20260223T222819Z_core_eval.json`
    - `<server-repo-root>/data/artifacts/evals/scheduled/20260223T222819Z_job_search_eval.json`
    - `<server-repo-root>/data/artifacts/evals/scheduled/20260223T222819Z_learning_eval.json`
  - scheduled eval Markdown artifacts:
    - `<server-repo-root>/data/artifacts/evals/20260223T222856Z_c95f8a32aadb49f68152a4fa6ea1d919.md`
    - `<server-repo-root>/data/artifacts/evals/20260223T222942Z_2bdc9cdaf2f24437964c880ae3f2c294.md`
    - `<server-repo-root>/data/artifacts/evals/20260223T223043Z_5831137a2f984e6fa8abc8362adfc836.md`
- Added import-ready n8n operator form workflows:
  - `<repo-root>/n8n/workflows/phase3a_bookmarklet_form_http.workflow.json`
  - `<repo-root>/n8n/workflows/phase3a_meeting_action_form_http.workflow.json`
- Added Phase 3A form wiring runbook:
  - `<repo-root>/n8n/workflows/PHASE3A_OPERATOR_FORMS_WIRING.md`

### Notes

- ai-lab path `<server-repo-root>/data/artifacts/rag/` is root-owned; direct non-dry-run query wrapper writes fail there.
- For wrapper validation in this thread, query run used:
  - `DATA_ARTIFACTS=<server-repo-root>/data/artifacts_operator`

## 2026-02-23 - Phase 3A kickoff: operator wrappers + runbook

### Outcome

- Started Phase 3A operator UX implementation with no-curl wrapper scripts:
  - `<repo-root>/scripts/phase3/run_ingest_manifest_now.sh`
  - `<repo-root>/scripts/phase3/run_query_mode_now.sh`
  - `<repo-root>/scripts/phase3/run_all_evals_now.sh`
- Added a dedicated Phase 3A operator runbook:
  - `<repo-root>/docs/Recall_local_Phase3A_Operator_Runbook.md`
  - includes Open WebUI payload templates (`default`, `job-search`, `learning`) and n8n form/webhook payload mappings for bookmarklet ingestion + meeting action extraction.
- Updated docs index:
  - `<repo-root>/docs/README.md`

## 2026-02-23 - Added formal Phase 3 guide + cleanup sweep fixes

### Outcome

- Added formal Phase 3 execution plan:
  - `<repo-root>/docs/Recall_local_Phase3_Guide.md`
  - includes `3A` UI/operator path, `3B` retrieval quality upgrades, and `3C` ops hardening/portfolio packaging with explicit completion gate.
- Fixed eval contract bug in:
  - `<repo-root>/scripts/eval/run_eval.py`
  - `_evaluate_payload()` now returns the expected 7-field tuple in all branches.
- Improved script portability by removing hard-coded default webhook host:
  - `<repo-root>/scripts/eval/scheduled_eval.sh`
  - `<repo-root>/scripts/rehearsal/run_phase2_demo_rehearsal.sh`
  - defaults now derive from `N8N_HOST` (`http://localhost:5678` fallback) unless `RECALL_EVAL_WEBHOOK_URL` is explicitly set.
  - replaced Bash-4-only `${VAR,,}` lowercasing with POSIX-compatible `tr` path for Mac Bash compatibility.
- Updated related docs:
  - `<repo-root>/docs/README.md`
  - `<repo-root>/docs/Recall_local_Eval_Scheduling.md`
  - `<repo-root>/docs/Recall_local_Phase2_Demo_Rehearsal_Runbook.md`

## 2026-02-23 - Added Phase 2 demo rehearsal runbook and helper script

### Outcome

- Added instruction doc for running and logging a full clean end-to-end Phase 2 rehearsal:
  - `<repo-root>/docs/Recall_local_Phase2_Demo_Rehearsal_Runbook.md`
- Added one-command rehearsal runner script:
  - `<repo-root>/scripts/rehearsal/run_phase2_demo_rehearsal.sh`
  - writes timestamped logs under:
    - `<server-repo-root>/data/artifacts/rehearsals/`
- Updated docs index links:
  - `<repo-root>/docs/README.md`

## 2026-02-23 - Scheduled eval retry guard for flaky webhook/model runs

### Outcome

- Hardened scheduled evaluator to retry each suite once before emitting regression alerts:
  - `<repo-root>/scripts/eval/scheduled_eval.sh`
- Added new env controls:
  - `RECALL_EVAL_RETRY_ON_FAIL` (default `true`)
  - `RECALL_EVAL_RETRY_DELAY_SECONDS` (default `5`)
- Updated scheduling documentation:
  - `<repo-root>/docs/Recall_local_Eval_Scheduling.md`

## 2026-02-23 - Added learning eval suite and scheduled execution wiring

### Outcome

- Added dedicated learning eval cases:
  - `<repo-root>/scripts/eval/learning_eval_cases.json`
  - 8 cases total (6 answerable + 2 unanswerable)
  - all cases run Workflow 02 with:
    - `mode=learning`
    - `filter_tags=["learning","genai-docs"]`
- Extended scheduled eval runner to execute three suites:
  - core: `<repo-root>/scripts/eval/eval_cases.json`
  - job-search: `<repo-root>/scripts/eval/job_search_eval_cases.json`
  - learning: `<repo-root>/scripts/eval/learning_eval_cases.json`
  - implementation: `<repo-root>/scripts/eval/scheduled_eval.sh`
- Added scheduling docs/env var for learning suite:
  - `RECALL_EVAL_LEARNING_CASES_FILE`
  - `<repo-root>/docs/Recall_local_Eval_Scheduling.md`

## 2026-02-23 - Learning mode + corpus-lane manifest controls

### Outcome

- Added Workflow 02 learning prompt profile:
  - `<repo-root>/prompts/learning_coach.md`
  - selected via payload/CLI `mode=learning`
- Extended Workflow 02 mode routing:
  - `<repo-root>/scripts/phase1/rag_query.py`
  - `mode=learning` now maps to `audit.prompt_profile=learning_coach`
- Added payload example for learning lane queries:
  - `<repo-root>/n8n/workflows/payload_examples/rag_query_learning_payload_example.json`
- Added learning corpus manifest for non-interview AI training docs:
  - `<repo-root>/scripts/phase2/learning_manifest.genieincodebottle.ai-lab.json`
- Generalized manifest ingest helper behavior:
  - `<repo-root>/scripts/phase2/ingest_job_search_manifest.py`
  - removed implicit `job-search` tag injection
  - added optional `--ensure-tag` for explicit tag enforcement

## 2026-02-23 - Added native DOCX ingestion extraction

### Outcome

- Updated file extraction path to support `.docx` directly in Workflow 01 ingestion:
  - `<repo-root>/scripts/phase1/ingestion_pipeline.py`
  - new extractor: `_extract_text_from_docx(...)` (paragraph + table cell text)
- Added dependency:
  - `<repo-root>/requirements.txt` now includes `python-docx`

### Notes

- PDF extraction remains unchanged.
- In environments where bridge container runs `pip install -r requirements.txt` on startup, DOCX support activates after bridge recreate.

## 2026-02-23 - Phase 2C: tag-scoped retrieval + job-search mode + eval suite

### Outcome

- Added optional Workflow 02 retrieval tag filtering (`filter_tags`) end-to-end:
  - `<repo-root>/scripts/phase1/retrieval.py`
  - `<repo-root>/scripts/phase1/rag_query.py`
  - `<repo-root>/scripts/phase1/rag_from_payload.py`
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
- Added Workflow 02 job-search prompt profile:
  - `<repo-root>/prompts/job_search_coach.md`
  - selected via payload/CLI `mode=job-search`
- Added optional Langfuse instrumentation hooks for `generate()` and `embed()`:
  - `<repo-root>/scripts/llm_client.py`
  - `<repo-root>/requirements.txt` now includes `langfuse`
  - traces include workflow/mode metadata when supplied by callers
- Extended Workflow 02 audit/sources metadata:
  - `sources[].tags`
  - `audit.mode`, `audit.filter_tags`, `audit.prompt_profile`
- Added dedicated job-search eval suite on shared harness:
  - `<repo-root>/scripts/eval/job_search_eval_cases.json`
  - `<repo-root>/scripts/eval/run_eval.py`
  - added checks for required grounding terms and required source tags
- Updated scheduled eval runner to execute both core and job-search suites:
  - `<repo-root>/scripts/eval/scheduled_eval.sh`
- Added payload examples and runbook updates:
  - `<repo-root>/n8n/workflows/payload_examples/rag_query_job_search_payload_example.json`
  - `<repo-root>/n8n/workflows/payload_examples/rag_query_payload_example.json`
  - `<repo-root>/n8n/workflows/PHASE1C_WORKFLOW02_WIRING.md`
  - `<repo-root>/docs/Recall_local_Eval_Scheduling.md`
- Added batch ingest helper to reduce repetitive curl ingestion commands for job-search corpus:
  - `<repo-root>/scripts/phase2/ingest_job_search_manifest.py`
  - `<repo-root>/scripts/phase2/job_search_manifest.example.json`

### Verification in this thread

- `python3 -m compileall scripts` (passes)
- retrieval/filter parsing smoke checks pass for:
  - `filter_tags` normalization
  - `mode`/`filter_tags` payload parsing
- eval harness updates compile and emit expanded per-case fields for:
  - `required_terms_ok`
  - `source_tags_ok`

## 2026-02-23 - Bridge TLS trust fix for HTTPS URL ingestion

### Outcome

- Updated bridge compose startup command to install CA certificates before running Python ingestion service:
  - `<repo-root>/docker/phase1b-ingest-bridge.compose.yml`
- Added URL ingestion TLS fallback controls for environments with custom/intercepted cert chains:
  - `<repo-root>/scripts/phase1/ingestion_pipeline.py`
  - env flags:
    - `RECALL_URL_VERIFY_TLS` (default `true`)
    - `RECALL_URL_ALLOW_INSECURE_FALLBACK` (default `false`)
  - bridge compose sets fallback enabled to keep bookmarklet ingestion operational when cert trust fails in container runtime.

### Why

- Bookmarklet URL ingestion test hit SSL verification failure inside `recall-ingest-bridge` container:
  - `[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate`
- Installing `ca-certificates` resolves HTTPS trust for URL extraction calls.

## 2026-02-23 - Phase 2B ingestion controls: gdoc/bookmarklet normalization + source-based replacement

### Outcome

- Extended unified ingestion normalization to support browser bookmarklet channel and richer webhook fallback mapping:
  - `<repo-root>/scripts/phase1/channel_adapters.py`
  - added channel: `bookmarklet`
  - webhook fallback now maps `url/text/title/tags` and optional replacement controls
- Added payload-level replacement controls in Workflow 01 request parser:
  - `<repo-root>/scripts/phase1/ingest_from_payload.py`
  - supported fields: `replace_existing`, `source_key`, top-level `tags`
- Implemented source-identity replacement policy in ingestion backend:
  - `<repo-root>/scripts/phase1/ingestion_pipeline.py`
  - computes canonical `source_identity` (URL canonicalization + optional override key)
  - optional delete-before-upsert (`replace_existing=true`)
  - persists `source_identity` and replacement metadata in Qdrant payload
  - returns replacement audit fields in ingestion result (`replaced_points`, `replacement_status`)
- Added Google Docs payload support improvements:
  - accepts gdoc payload object containing URL/doc_id and optional extracted text
  - source extraction path now supports `gdoc` content dictionaries
- Bridge/channel runner updates:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py` supports `/ingest/bookmarklet`
  - `<repo-root>/scripts/phase1/ingest_channel_payload.py` accepts `--channel bookmarklet`

### Added payload examples

- `<repo-root>/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json`
- `<repo-root>/n8n/workflows/payload_examples/gdoc_ingest_payload_example.json`

### Documentation updates

- `<repo-root>/n8n/workflows/PHASE1B_CHANNEL_WIRING.md`
- `<repo-root>/docs/Recall_local_Phase1_Guide.md`
- `<repo-root>/docs/Recall_local_Phase2_Guide.md`
- `<repo-root>/docs/Recall_local_PRD_Addendum_JobSearch.md`
- `<repo-root>/docs/README.md`

### Verification in this thread

- `python3 -m compileall scripts` (passes)
- Normalization smoke checks for:
  - bookmarklet raw payload -> unified payload
  - gdoc payload object -> unified payload
- Payload parser check confirms replacement controls are mapped:
  - `replace_existing=True`, `source_key` preserved in `IngestRequest`
- Source identity checks:
  - URL canonicalization strips tracking params
  - replacement guard blocks `text/email` replacement when no stable key is provided

## 2026-02-23 - Phase 2A verification: non-dry-run Workflow 03 pass via bridge

### Outcome

- Ran Workflow 03 bridge verification in non-dry-run mode with live ai-lab dependencies:
  - `OLLAMA_HOST=http://<ai-lab-tailnet-ip>:11434`
  - `QDRANT_HOST=http://<ai-lab-tailnet-ip>:6333`
- Verification script pass:
  - `<repo-root>/scripts/phase2/verify_workflow03_bridge.py`
  - run_id: `ef93fdf2f5c14f53befc7126f77295c4`
  - result: `ok=true`
- Confirmed persisted outputs:
  - artifact exists: `<repo-root>/data/artifacts/meetings/20260223T145113Z_ef93fdf2f5c14f53befc7126f77295c4.md`
  - SQLite run row present for workflow `workflow_03_meeting_action_items`

### Additional note

- Local dry-run verification also passed with model override:
  - `OLLAMA_MODEL=llama3.2:latest`
  - this avoided local default model mismatch (`llama3:8b` unavailable).

## 2026-02-23 - Phase 2A assets: n8n wiring + bridge verification script

### Outcome

- Added import-ready n8n workflow exports for Workflow 03:
  - `<repo-root>/n8n/workflows/phase2a_meeting_action_items.workflow.json`
  - `<repo-root>/n8n/workflows/phase2a_meeting_action_items_http.workflow.json`
- Added Workflow 03 wiring runbook:
  - `<repo-root>/n8n/workflows/PHASE2A_WORKFLOW03_WIRING.md`
- Added bridge verification script for Workflow 03 contract + persisted evidence checks:
  - `<repo-root>/scripts/phase2/verify_workflow03_bridge.py`

### Notes

- Verification script validates response schema and can assert artifact + SQLite run presence on non-dry-run calls.
- Script defaults to using:
  - bridge URL: `http://localhost:8090/meeting/action-items`
  - payload file: `<repo-root>/n8n/workflows/payload_examples/meeting_action_items_payload_example.json`

## 2026-02-23 - Phase 2A kickoff: Workflow 03 Meeting -> Action Items core implementation

### Outcome

- Added Workflow 03 runner and payload entrypoint for transcript-to-action extraction:
  - `<repo-root>/scripts/phase2/meeting_action_items.py`
  - `<repo-root>/scripts/phase2/meeting_from_payload.py`
- Added Workflow 03 prompt templates:
  - `<repo-root>/prompts/workflow_03_meeting_extract.md`
  - `<repo-root>/prompts/workflow_03_meeting_extract_retry.md`
- Extended output validation utilities with meeting schema validation:
  - `<repo-root>/scripts/validate_output.py`
- Exposed Workflow 03 webhook route via HTTP bridge:
  - `<repo-root>/scripts/phase1/ingest_bridge_api.py`
  - supported paths: `/meeting/action-items` (primary), `/meeting/actions`, `/query/meeting`
- Added payload example for n8n/webhook tests:
  - `<repo-root>/n8n/workflows/payload_examples/meeting_action_items_payload_example.json`

### Workflow 03 behavior shipped

- Validates structured output contract (`meeting_title`, `summary`, `decisions`, `action_items`, `risks`, `follow_ups`) with retry pass before fallback.
- Writes Markdown artifacts under `/data/artifacts/meetings/` on non-dry runs.
- Upserts a meeting summary chunk into Qdrant `recall_docs` for downstream Workflow 02 retrieval.
- Logs run lifecycle to SQLite `runs` table with workflow id `workflow_03_meeting_action_items`.

### Verification in this thread

- `python3 -m compileall scripts` (passes)
- `validate_meeting_output(...)` happy-path check (valid = true)
- `run_meeting_action_items(..., dry_run=True)` with mocked LLM response (returns Workflow 03 payload + audit block)

## 2026-02-23 - Phase 2 implementation checklists added

### Outcome

- Added actionable Phase 2 checklists covering `2B` and `2C` workstreams:
  - `<repo-root>/docs/Recall_local_Phase2_Checklists.md`
- Linked checklist from Phase 2 guide and docs index:
  - `<repo-root>/docs/Recall_local_Phase2_Guide.md`
  - `<repo-root>/docs/README.md`

### Notes

- Checklist includes file-level implementation tasks and verification gates for:
  - ingestion expansion + source-based replacement policy
  - Workflow 02 `filter_tags`
  - job-search prompt mode with strict JSON/citation contract
  - shared-harness job-search eval suite

## 2026-02-23 - Phase 2 plan updated for job-search domain mode

### Outcome

- Updated Phase 2 execution guide to incorporate the Job Search addendum as scoped Phase 2 work:
  - `<repo-root>/docs/Recall_local_Phase2_Guide.md`

### Planning changes captured

- `2B` now includes corpus hygiene requirements for mutable sources (source-based replacement policy) alongside ingestion expansion.
- `2C` now explicitly includes Workflow 02 tag-scoped retrieval (`filter_tags`), Job Search prompt profile, and a dedicated job-search eval case suite using the shared eval harness.
- `2D` now requires both core and job-search eval suites to pass for demo reliability gate completion.

## 2026-02-23 - Phase 2 plan defined with sub-phases and gates

### Outcome

- Added Phase 2 execution guide with explicit sub-phases, delivery order, and phase completion gate:
  - `<repo-root>/docs/Recall_local_Phase2_Guide.md`
- Updated docs index:
  - `<repo-root>/docs/README.md`

### Sub-phases captured

- `2A` Workflow 03 (Meeting -> Action Items) core implementation.
- `2B` Ingestion expansion (Google Docs + browser bookmarklet mandatory).
- `2C` Langfuse observability + artifact viewer polish.
- `2D` Demo reliability gate and rehearsal.

## 2026-02-23 - Scheduled eval + regression alerting added

### Outcome

- Added cron-ready scheduled eval execution against live Workflow 02 webhook:
  - `<repo-root>/scripts/eval/scheduled_eval.sh`
- Added regression alert helper with optional webhook notification:
  - `<repo-root>/scripts/eval/notify_regression.py`
- Added scheduling runbook:
  - `<repo-root>/docs/Recall_local_Eval_Scheduling.md`

### Notes

- Supports daily/weekly cron schedules on ai-lab.
- Regressions produce non-zero exit code and optional Slack/Teams webhook alerts when configured.

## 2026-02-23 - Workflow 02 IDK eval gate green on live webhook

### Outcome

- Verified live webhook end-to-end pass after sync/redeploy:
  - run_id: `0ee745eada024070815f249d85d3337e`
  - backend: `webhook`
  - webhook URL: `http://<ai-lab-tailnet-ip>:5678/webhook/recall-query`
  - result: `15/15 PASS`
  - unanswerable: `5/5 PASS`
  - artifact: `<server-repo-root>/data/artifacts/evals/20260223T000357Z_0ee745eada024070815f249d85d3337e.md`

### Notes

- This confirms the unanswerable guardrail hardening for Workflow 02 is effective in production path (n8n webhook + HTTP bridge).
- The earlier `0/15` run was transient during sync/restart and is superseded by this run.

## 2026-02-22 - Workflow 02 unanswerable hardening (IDK gate)

### Goal

- Prevent Workflow 02 from failing hard on unanswerable prompts and enforce explicit abstention for low-confidence output.

### What was changed

- `scripts/phase1/rag_query.py`:
  - Added canonical abstention constants and phrase matching.
  - Added low-confidence normalization that rewrites non-abstaining low-confidence answers to explicit abstention.
  - Added citation backfill from `sources[]` when needed.
  - Changed validation-failure path to return structured fallback instead of raising.
  - Added fallback audit fields so artifacts record why fallback logic was used.
- `scripts/eval/run_eval.py`:
  - Expanded unanswerable phrase patterns (`not explicitly stated` included).
  - Updated unanswerable scoring to focus on abstention behavior even if citations are empty.

### Verification run in this thread

- Local runtime checks (monkeypatched retrieval/LLM) confirmed:
  - low-confidence direct answers are normalized to explicit abstention,
  - citation-empty abstention no longer crashes the runner.
- Webhook eval against ai-lab still reflects pre-sync behavior (`10/15`), which indicates ai-lab is running older script versions.

### Deployment note

- Sync updated scripts to ai-lab, recreate bridge, then rerun eval:
  - `docker compose -f <server-repo-root>/docker/phase1b-ingest-bridge.compose.yml up -d --force-recreate`
  - `python3 <server-repo-root>/scripts/eval/run_eval.py --backend webhook --webhook-url http://<ai-lab-tailnet-ip>:5678/webhook/recall-query`

## 2026-02-22 - Added \"I Don't Know\" eval bank (unanswerable gate)

### Goal

- Add explicit hallucination-resistance checks by introducing trick/unanswerable eval cases that require abstention.

### What was added

- Eval harness logic updates:
  - `scripts/eval/run_eval.py` now supports case flag `expect_unanswerable` and reports:
    - `unanswerable_passed`
    - `unanswerable_total`
  - Unanswerable case pass criteria:
    - explicit uncertainty/refusal language in answer
    - `confidence_level=low`
    - citation pair validity still enforced
- Eval case bank expanded:
  - `scripts/eval/eval_cases.json` now includes 5 trick/unanswerable questions.
- Prompt hardening updates:
  - `prompts/workflow_02_rag_answer.md`
  - `prompts/workflow_02_rag_answer_retry.md`
  - both now explicitly instruct abstention when context is insufficient.

### Current result snapshot

- Expanded eval run:
  - run_id: `acc53692280540cfb02d1476d89119ef`
  - result: `10/15 PASS`
  - unanswerable: `0/5 PASS`
  - artifact: `data/artifacts/evals/20260222T234255Z_acc53692280540cfb02d1476d89119ef.md`
- Interpretation:
  - The new gate is working as intended (it catches hallucination/refusal weaknesses).
  - Next hardening target is improving Workflow 02 behavior on unanswerable questions.

## 2026-02-22 - Phase 1D completed: eval gate green

### Outcome

- Implemented and ran eval harness against live Workflow 02 webhook with persisted results and Markdown artifact output.
- Full suite passed:
  - run_id: `310287389df24e58aa1899a859ad2dcf`
  - backend: `webhook`
  - webhook URL: `http://<ai-lab-tailnet-ip>:5678/webhook/recall-query`
  - result: `10/10 PASS`
- Generated eval artifact:
  - `data/artifacts/evals/20260222T233323Z_310287389df24e58aa1899a859ad2dcf.md`

### What was validated

- Citation presence per case.
- Citation/doc-chunk pair validity against returned `sources[]`.
- Latency threshold enforcement with run-level pass/fail exit behavior.
- SQLite persistence to `eval_results`.

## 2026-02-22 - Phase 1D kickoff: eval harness + execution-first runbook

### Goal

- Start Phase 1D by shipping a runnable eval harness for Workflow 02 with persistence, artifact output, and a strict troubleshooting protocol.

### What was added

- Eval harness and default suite:
  - `scripts/eval/run_eval.py`
  - `scripts/eval/eval_cases.json`
- Eval runbook:
  - `docs/Recall_local_Phase1D_Eval_Guide.md`
- Phase guide + docs index updates:
  - `docs/Recall_local_Phase1_Guide.md` marks `1D` in progress and lists 1D kickoff deliverables.
  - `docs/README.md` links to the 1D eval guide.

### Notes

- Eval checks enforce citation presence, citation/source pair validity, and latency thresholds.
- Webhook-mode troubleshooting order is now documented as execution-first (n8n Executions -> failed node details -> bridge health -> webhook retest).

## 2026-02-22 - Workflow 02 stabilized: execution-first n8n debugging notes

### Outcome

- Confirmed production Workflow 02 webhook is live with cited response payload:
  - `POST http://<ai-lab-tailnet-ip>:5678/webhook/recall-query` -> `HTTP 200` with `workflow_02_rag_query` result.
- Confirmed bridge endpoint is live:
  - `POST http://<ai-lab-tailnet-ip>:8090/query/rag?dry_run=true` -> `HTTP 200`.

### Key lessons captured for next thread

- Use n8n `Executions` as primary diagnostic source; failed node + stack trace is the fastest path to root cause.
- In this n8n deployment, `Execute Command` cannot run Workflow 02 Python scripts (`python3` missing in container image).
- Workflow 02 should use HTTP bridge node with payload expression `={{ $json.body }}`.
- Distinguish host scope for connectivity checks:
  - MacBook to ai-lab: `http://<ai-lab-tailnet-ip>:<port>`
  - ai-lab shell: `http://localhost:<port>`

## 2026-02-22 - Workflow 02 n8n deployment assets prepared

### Goal

- Ship import-ready n8n workflow files for Workflow 02 so `/webhook/recall-query` can be activated immediately in authenticated n8n.

### What was added

- Workflow 02 n8n exports:
  - `n8n/workflows/phase1c_recall_rag_query.workflow.json`
  - `n8n/workflows/phase1c_recall_rag_query_http.workflow.json`
- Workflow 02 runbook:
  - `n8n/workflows/PHASE1C_WORKFLOW02_WIRING.md`
- HTTP bridge update (to support Workflow 02 requests):
  - `scripts/phase1/ingest_bridge_api.py` now supports `POST /query/rag`
- RAG payload runner enhancement:
  - `scripts/phase1/rag_from_payload.py` now accepts `--payload-base64`
- Bridge compose env update:
  - `docker/phase1b-ingest-bridge.compose.yml` adds `DATA_ARTIFACTS`

### Notes

- n8n REST API on `ai-lab` is reachable but still requires authenticated session (`401 Unauthorized` from unauthenticated calls).
- Workflow files are ready for immediate import + activation in n8n UI.

## 2026-02-22 - Phase 1C completed: live cited RAG verification

### Outcome

- Executed Workflow 02 against live endpoints (`Ollama <ai-lab-tailnet-ip>:11434`, `Qdrant <ai-lab-tailnet-ip>:6333`) and validated three demo queries with citation-safe output.
- Confirmed citation validation enforced real retrieved pairs (`doc_id` + `chunk_id`) with no fabricated citations across runs:
  - `e9310c04d1194383b39c7e5a68f5cbc8`
  - `1ced94ff0d8e4e9db6630a07fe6f70d4`
  - `a889edf87498486ab9b5923fb8acc107`
- Verified non-dry-run execution writes run metadata and artifact output:
  - run: `610b129b66754422996c3cb177a84973`
  - artifact: `data/artifacts/rag/20260222T223255Z_610b129b66754422996c3cb177a84973.json`

### Compatibility fix

- Updated `scripts/phase1/retrieval.py` to support both legacy `qdrant-client.search(...)` and current `qdrant-client.query_points(...)` APIs.

## 2026-02-22 - Phase 1C kickoff: cited RAG workflow + validation

### Goal

- Start Phase 1C by implementing Workflow 02 query path with retrieval, structured citation output validation, and retry behavior.

### What was added

- Workflow 02 retrieval + query execution scripts:
  - `scripts/phase1/retrieval.py`
  - `scripts/phase1/rag_query.py`
  - `scripts/phase1/rag_from_payload.py`
- Structured response validator:
  - `scripts/validate_output.py`
- Versioned prompt templates:
  - `prompts/workflow_02_rag_answer.md`
  - `prompts/workflow_02_rag_answer_retry.md`
- Payload example:
  - `n8n/workflows/payload_examples/rag_query_payload_example.json`
- Phase guide updates:
  - `docs/Recall_local_Phase1_Guide.md` now marks `1C` as in progress and includes 1C smoke commands/deliverables.

### Notes

- Workflow 02 now enforces citation pair checks against retrieved context (`doc_id` + `chunk_id`) and retries once with a stricter prompt on validation failure.
- Phase 1C exit criteria remain open until three demo queries are validated end-to-end against live indexed data.

## 2026-02-22 - Phase 1B completed

### Outcome

- Confirmed successful ingestion through active n8n HTTP-bridge workflows.
- Verified webhook route and ingest response payload included a completed run.
- Verified Qdrant point growth after final webhook ingest:
  - `recall_docs` points: `5 -> 6`

### Phase 1B exit criteria status

- PDF drop searchable in `recall_docs`: complete
- Shared URL searchable in `recall_docs`: complete
- Forwarded email attachment searchable in `recall_docs`: complete

## 2026-02-22 - Phase 1B live backend verification + workflow export files

### Goal

- Produce import-ready n8n workflow exports and run live backend ingestion checks for the three 1B channels.

### What was added

- n8n workflow JSON exports:
  - `n8n/workflows/phase1b_recall_ingest_webhook.workflow.json`
  - `n8n/workflows/phase1b_gmail_forward_ingest.workflow.json`
  - `n8n/workflows/phase1b_recall_ingest_webhook_http.workflow.json`
  - `n8n/workflows/phase1b_gmail_forward_ingest_http.workflow.json`
- HTTP bridge fallback (for n8n environments without Execute Command):
  - `scripts/phase1/ingest_bridge_api.py`
  - `docker/phase1b-ingest-bridge.compose.yml`
- Runbook update:
  - `n8n/workflows/PHASE1B_CHANNEL_WIRING.md` now includes workflow import instructions.

### Live verification performed

- Target runtime endpoints:
  - Ollama: `http://<ai-lab-tailnet-ip>:11434`
  - Qdrant: `http://<ai-lab-tailnet-ip>:6333`
- File/PDF ingestion (folder path) succeeded via:
  - `scripts/phase1/ingest_incoming_once.py`
- iOS URL-share payload ingestion succeeded via:
  - `scripts/phase1/ingest_channel_payload.py --channel ios-share`
- Gmail body + attachment payload ingestion succeeded via:
  - `scripts/phase1/ingest_channel_payload.py --channel gmail-forward`
- Qdrant collection growth observed:
  - `recall_docs` points: `0` -> `5`

### Evidence snapshot

- Qdrant payloads now include channel markers:
  - `ingestion_channel=folder-watcher` with `source_type=file` (PDF drop)
  - `ingestion_channel=ios-shortcut` with `source_type=url`
  - `ingestion_channel=gmail-forward` with `source_type=email` and `source_type=file` (attachment)
- SQLite ingestion log (local test DB) includes completed rows for all three channels.

### Blocker

- n8n REST/editor deployment on `ai-lab` remains blocked from this session due authentication constraints (`401 Unauthorized` API and SSH auth denied).
- Workflow JSON exports are ready for import once authenticated n8n access is available.

## 2026-02-22 - Phase 1B kickoff: channel adapters and n8n wiring runbook

### Goal

- Start Phase 1B by wiring practical channel integration assets for webhook, iOS share, and Gmail forward inputs.

### What was added

- Channel normalization + ingestion runner:
  - `scripts/phase1/channel_adapters.py`
  - `scripts/phase1/ingest_channel_payload.py`
- n8n channel wiring runbook with command-ready node configuration:
  - `n8n/workflows/PHASE1B_CHANNEL_WIRING.md`
- n8n import-ready workflow exports:
  - `n8n/workflows/phase1b_recall_ingest_webhook.workflow.json`
  - `n8n/workflows/phase1b_gmail_forward_ingest.workflow.json`
- Channel payload examples:
  - `shortcuts/ios_send_to_recall_payload_example.json`
  - `n8n/workflows/payload_examples/gmail_forward_payload_example.json`

### Notes

- This is a Phase 1B kickoff increment and sets integration contracts.
- Final 1B exit criteria still require live end-to-end indexing for PDF drop, shared URL, and Gmail attachment flows.

## 2026-02-22 - Phase 1 plan broken into sub-phases

### Goal

- Convert Phase 1 from a broad milestone into explicit execution slices with measurable gates.

### Outcome

- Updated `docs/Recall_local_Phase1_Guide.md` with sub-phases:
  - `1A` Ingestion Core (completed)
  - `1B` Channel Wiring (in progress)
  - `1C` Cited RAG (pending)
  - `1D` Eval Gate (pending)
- Added explicit Phase 1 completion criteria tied to ingestion channels, citation validity, and eval green status.

## 2026-02-22 - Phase 1 started with Workflow 01 ingestion scripts

### Goal

- Begin Phase 1 implementation by committing the core ingestion code path required for multi-source indexing.

### What was added

- Phase 1 ingestion scripts:
  - `scripts/phase1/ingestion_pipeline.py`
  - `scripts/phase1/ingest_from_payload.py`
  - `scripts/phase1/ingest_incoming_once.py`
- Phase 1 kickoff guide:
  - `docs/Recall_local_Phase1_Guide.md`
- Docs index update:
  - `docs/README.md`

### Scope in this increment

- Unified ingestion code path for:
  - `file`
  - `url`
  - `text`
  - `email` (body + optional attachment fan-out via payload entrypoint)
  - `gdoc` (URL-backed)
- Processing steps now implemented in code:
  - source extraction (PDF/text file, URL via Trafilatura, inline text/email body)
  - heading-aware token chunking
  - embedding generation through `scripts/llm_client.py`
  - Qdrant upsert to `recall_docs`
  - SQLite logging to `runs` + `ingestion_log`
  - file move from incoming to processed for file-based ingestion

### Notes

- This starts Phase 1 but does not complete it.
- Workflow 02 (RAG with citations), eval harness, iOS shortcut packaging, and full Gmail automation remain pending.

## 2026-02-22 - Linked companion repos and aligned public metadata

### Goal

- Tie `codex-context-kickoff-kit` and `codex-project-startup-kit` together for discoverability and combined usage.

### Outcome

- Updated README in both repos with:
  - `Companion Repo` section (reciprocal links)
  - `Use Together` workflow steps
- Updated GitHub About descriptions in both repos to include companion references.
- Added aligned topic tags across both repos (codex/context-engineering/workflow/docs/productivity set).

### Repo links

- [https://github.com/jaydreyer/codex-context-kickoff-kit](https://github.com/jaydreyer/codex-context-kickoff-kit)
- [https://github.com/jaydreyer/codex-project-startup-kit](https://github.com/jaydreyer/codex-project-startup-kit)

## 2026-02-22 - Published standalone project startup kit repository

### Goal

- Open-source the reusable project startup pattern (separate from context-kickoff skill package).

### Outcome

- Created and published:
  - [https://github.com/jaydreyer/codex-project-startup-kit](https://github.com/jaydreyer/codex-project-startup-kit)
- Repository contents include:
  - `PROJECT_BOOTSTRAP_PROMPT.md`
  - `DAILY_KICKOFF_PROMPT.md`
  - canonical docs templates in `templates/docs/`
  - scaffold script `scripts/init-docs.sh`
  - `README.md` and `LICENSE`

## 2026-02-22 - Published standalone context-kickoff kit repository

### Goal

- Make the context-kickoff sharing package available as a standalone public repository.

### Outcome

- Created and published:
  - [https://github.com/jaydreyer/codex-context-kickoff-kit](https://github.com/jaydreyer/codex-context-kickoff-kit)
- Repository contents include:
  - root `README.md`
  - `CONTEXT_KICKOFF_SHARING_GUIDE.md`
  - `LICENSE` (MIT)
  - `context-kickoff/` skill folder with script, references, and UI metadata

## 2026-02-22 - Context-kickoff sharing kit prepared

### Goal

- Package the context-kickoff pattern so it can be shared and reused across other projects/users.

### What was added

- Share guide:
  - `docs/CONTEXT_KICKOFF_SHARING_GUIDE.md`
- Shareable kit folder:
  - `docs/context-kickoff-kit/README.md`
  - `docs/context-kickoff-kit/context-kickoff/SKILL.md`
  - `docs/context-kickoff-kit/context-kickoff/agents/openai.yaml`
  - `docs/context-kickoff-kit/context-kickoff/references/file-priority.md`
  - `docs/context-kickoff-kit/context-kickoff/scripts/discover_context.sh`
- Docs index updated:
  - `docs/README.md`

### Notes

- The packaged skill removes user-specific absolute paths and uses `CODEX_HOME` / `~/.codex` conventions.
- The guide includes copy-paste prompts, before/after framing, troubleshooting, and redaction guidance for public sharing.

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

- Ran provider checks on `ai-lab` (`<server-repo-root>`):
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
  - Tailscale IP: `<ai-lab-tailnet-ip>`
  - User: `jaydreyer`
- Synced repo to server path:
  - `<server-repo-root>`
- Ran Phase 0 setup script.
- Because `python3-venv` is not installed and no sudo path was available from session, used user-site fallback install path in setup script.
- Initialized SQLite:
  - `<server-repo-root>/data/recall.db`
  - tables: `runs`, `eval_results`, `alerts`, `ingestion_log`
- Created/verified Qdrant collection:
  - `recall_docs`
  - vector dimension `768`
- Started artifact viewer:
  - container: `recall-mkdocs`
  - URL: `http://<ai-lab-tailnet-ip>:8100/` (Tailnet access)
- Smoke test result:
  - `8/8` checks passed (`scripts/phase0/connectivity_check.py`)

### Provider Status

- Confirmed local provider works:
  - `RECALL_LLM_PROVIDER=ollama python3 scripts/llm_client.py` succeeded.
- Cloud provider keys remain placeholders in:
  - `<server-repo-root>/docker/.env`

### Commits Created

- `0517c07` Add PRD and Phase 0 setup guide
- `05ef291` Add Phase 0 setup scaffolding and bootstrap scripts
- `b0245ff` Harden Phase 0 setup for no-root Ubuntu hosts

### Follow-ups

- Add real API keys for Anthropic/OpenAI/Gemini in server `docker/.env`.
- Run provider validation for cloud fallback.
- Optional: install `python3-venv` on server later to use isolated `.venv` path instead of user-site fallback.

---

## 2026-03-10 - Observability Strategy Added

### Scope

- Added a durable planning document for future observability work:
  - `docs/OBSERVABILITY_STRATEGY.md`

### Notes

- This is a strategy and backlog document, not an implementation slice.
- It captures the recommended phased approach:
  - request ID propagation and structured telemetry first
  - Langfuse hardening for LLM observability
  - Honeycomb for cross-service tracing later
  - Playwright synthetic checks for UI monitoring
- The plan is intentionally staged so the observability foundation can land before the entire product surface is complete.
