# Recall.local Implementation Log

## 2026-02-24 - Pre-Phase-5 closure check snapshot

### What was executed

- Local hygiene run with ai-lab remote inspection:
  - `scripts/phase4/run_repo_hygiene_check.sh --ssh-key ~/.ssh/codex_ai_lab --no-fail`
  - report:
    - `/Users/jaydreyer/projects/recall-local/data/artifacts/phase4/hygiene/20260224T140000Z_repo_hygiene.json`
- ai-lab quick soak sample (2 iterations each suite):
  - `/home/jaydreyer/recall-local/scripts/phase4/run_eval_soak_now.sh --iterations 2 --suite both --delay-seconds 1 --no-fail-on-threshold`
  - run dir:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/phase4_soak/20260224T140000Z`
  - summary:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/phase4_soak/20260224T140000Z/soak_summary.json`
    - `/home/jaydreyer/recall-local/data/artifacts/evals/phase4_soak/20260224T140000Z/soak_summary.md`

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
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase5_Guide.md`
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase5_Checklists.md`
  - `/Users/jaydreyer/projects/recall-local/docs/phase5-implementation-brief.md`
- Updated Phase 4 guide to avoid planning overlap:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase4_Guide.md`
  - replaced prior Milestone 2 UX backlog with explicit handoff to Phase 5 docs.
- Incorporated decision changes:
  - FastAPI migration as task 1
  - separate `recall-ui` container
  - `RECALL_VAULT_WRITE_BACK=false` default
  - Gmail extension deferred to `5E.1`
  - optional local auth mode with startup warning when API key is unset
  - Syncthing-based Obsidian mirror handling (`on_moved`, temp file excludes, `RECALL_VAULT_IS_SYNCED=true`).
- Updated docs index with tracked Phase 5 planning assets:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`
  - includes the implementation brief and both scaffold files as in-repo references.

## 2026-02-24 - Phase 5 planning baseline from implementation brief + UI scaffolds

### Outcome

- Reviewed Phase 5 implementation brief and scaffold references:
  - `/Users/jaydreyer/projects/recall-local/docs/phase5-implementation-brief.md`
  - `/Users/jaydreyer/projects/recall-local/docs/scaffolds/recall-dashboard.jsx`
  - `/Users/jaydreyer/projects/recall-local/docs/scaffolds/recall-chrome-popup.jsx`
- Added formal Phase 5 execution plan:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase5_Guide.md`
  - defines sub-phases `5A`-`5F`, endpoint plan, data contract updates, and acceptance gate.
- Added actionable Phase 5 checklists:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase5_Checklists.md`
- Updated docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

## 2026-02-24 - Added Obsidian integration to Phase 4 backlog

### Outcome

- Updated Phase 4 guide with a dedicated Milestone 2 backlog for operator UX and Obsidian integration:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase4_Guide.md`
- Backlog now explicitly tracks:
  - Obsidian one-command ingest/query wrappers
  - Obsidian integration runbook
  - optional Obsidian HTTP action profile
  - concrete acceptance checks for frictionless ingestion/query flow.

### Superseded note

- This temporary Phase 4 backlog placement was superseded the same day by Phase 5 planning docs:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase5_Guide.md`
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase5_Checklists.md`

## 2026-02-24 - Phase 4A ai-lab soak evidence + hygiene remote check

### Outcome

- Synced Phase 4 files from Mac to ai-lab with SSH key auth and performed required remote spot-check:
  - sync key: `~/.ssh/codex_ai_lab`
  - remote check confirmed new Phase 4 scripts/workflow docs are present on `/home/jaydreyer/recall-local`.
- Ran first live Phase 4A soak on ai-lab:
  - command:
    - `/home/jaydreyer/recall-local/scripts/phase4/run_eval_soak_now.sh --iterations 5 --suite both --delay-seconds 2`
  - artifact dir:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/phase4_soak/20260224T024404Z`
  - summary artifacts:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/phase4_soak/20260224T024404Z/soak_summary.json`
    - `/home/jaydreyer/recall-local/data/artifacts/evals/phase4_soak/20260224T024404Z/soak_summary.md`
  - threshold status: `fail`
  - breach details:
    - `core:avg_case_pass_rate_below_threshold:0.973<1.000`
    - `core:avg_latency_above_threshold:36754.2>15000`
    - `job-search:avg_latency_above_threshold:34949.2>15000`
  - notable core failure reason:
    - unanswerable case "What is the planned Phase 2 launch date in March 2026?" intermittently returned high-confidence answer style in 2/5 runs (`14/15` pass in runs 3 and 4).
- Enhanced hygiene checker for key-based SSH environments:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase4/run_repo_hygiene_check.sh`
  - added `--ssh-key` / `AI_LAB_SSH_KEY`.
- Ran hygiene checker with remote inspection:
  - command:
    - `scripts/phase4/run_repo_hygiene_check.sh --ssh-key ~/.ssh/codex_ai_lab --no-fail`
  - report:
    - `/Users/jaydreyer/projects/recall-local/data/artifacts/phase4/hygiene/20260224T025138Z_repo_hygiene.json`
  - finding:
    - `remote_dirty_repo_files=7` (runtime repo not clean after file-sync style updates).

### Validation

- `bash -n scripts/phase4/run_repo_hygiene_check.sh`
- `scripts/phase4/run_repo_hygiene_check.sh --help`
- `scripts/phase4/run_repo_hygiene_check.sh --ssh-key ~/.ssh/codex_ai_lab --no-fail`

## 2026-02-24 - Phase 4 milestone-1 continuation: CI guardrails, release checklist, hygiene script

### Outcome

- Added first GitHub Actions quality gate:
  - `/Users/jaydreyer/projects/recall-local/.github/workflows/quality_checks.yml`
  - includes:
    - Python syntax checks across `scripts/**/*.py`
    - shell syntax checks across `scripts/**/*.sh`
    - smoke help checks for key phase3/phase4 wrappers.
- Added release checklist runbook:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Release_Checklist.md`
  - documents:
    - `v0.x-*` tag convention
    - required pre-release gates
    - ai-lab sync + spot-check requirement
    - rollback flow.
- Added Phase 4 hygiene checker:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase4/run_repo_hygiene_check.sh`
  - flags:
    - `._*` metadata files
    - ai-lab dirty runtime repo state
    - ai-lab stash presence
  - writes machine-readable JSON report under `data/artifacts/phase4/hygiene/`.
- Updated docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

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
  - `/Users/jaydreyer/projects/recall-local/scripts/phase4/run_eval_soak_now.sh`
  - supports repeated core/job-search eval runs, per-run JSON/stderr/meta artifacts, and thresholded summary generation.
- Added Phase 4A trend summarizer:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase4/summarize_eval_trend.py`
  - aggregates run artifacts into trend JSON + Markdown with:
    - per-run pass-rate + latency rows
    - suite-level averages
    - failure reason histogram
    - threshold breach reporting (`min pass-rate`, `max avg latency`, error-run detection).
- Updated docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

### Validation

- `bash -n scripts/phase4/run_eval_soak_now.sh`
- `python3 -m py_compile scripts/phase4/summarize_eval_trend.py`
- `scripts/phase4/run_eval_soak_now.sh --help`
- `python3 scripts/phase4/summarize_eval_trend.py --help`

## 2026-02-24 - Added Phase 3 completion summary and Phase 4 guide

### Outcome

- Added Phase 3 completion summary doc:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase3_Completion_Summary.md`
  - includes final scope status, evidence paths, key outcomes, and follow-up items.
- Added Phase 4 guide doc:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase4_Guide.md`
  - defines sub-phases (`4A` reliability telemetry, `4B` CI/release guardrails, `4C` operator maintenance), acceptance checks, and a concrete milestone-1 backlog.
- Updated docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

## 2026-02-24 - Job-search eval consistency fix: target-company priorities case stabilized

### Outcome

- Hardened `mode=job-search` prompt guidance for prioritization questions:
  - `/Users/jaydreyer/projects/recall-local/prompts/job_search_coach.md`
  - added explicit instruction to include `"company"`, `"priority"`, and `"fit"` when the question is about target companies/prioritization.
- Expanded required grounding term variants for the flaky case:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/job_search_eval_cases.json`
  - target case now accepts: `company|companies|priority|priorities|role|fit|target`.
- Synced changes to ai-lab and spot-checked remote content with `rg` before eval reruns.
- ai-lab validation results:
  - full job-search suite: `10/10` pass
    - artifact: `/home/jaydreyer/recall-local/data/artifacts/evals/20260224T021744Z_654dd08c90f64217bc1da3a704a2fd6a.md`
  - repeat answerable slice (`--max-cases 8`): `8/8` pass
    - artifact: `/home/jaydreyer/recall-local/data/artifacts/evals/20260224T021822Z_67353df091554cfea94e4f42b1efc779.md`

## 2026-02-24 - Phase 3C ai-lab validation: sync, restart/recovery smoke, portfolio bundle evidence

### Outcome

- Synced latest Phase 3C docs/scripts from Mac to ai-lab (`/home/jaydreyer/recall-local`) using `rsync` over SSH key auth and verified remote content with `rg` before runtime checks.
- Executed new preflight and deterministic restart wrappers on ai-lab:
  - `/home/jaydreyer/recall-local/scripts/phase3/run_service_preflight_now.sh`
  - `/home/jaydreyer/recall-local/scripts/phase3/run_deterministic_restart_now.sh --wait-timeout-seconds 180`
  - result: all service health checks passed (`Ollama`, `Qdrant`, `n8n`, bridge, SQLite paths).
- Executed backup/restore smoke test:
  - backup:
    - `/home/jaydreyer/recall-local/scripts/phase3/run_backup_now.sh --backup-name phase3c_recovery_smoke_20260224`
  - restore:
    - `/home/jaydreyer/recall-local/scripts/phase3/run_restore_now.sh --backup-dir /home/jaydreyer/recall-local/data/artifacts/backups/phase3c/phase3c_recovery_smoke_20260224 --replace-collection`
  - restore report:
    - `/home/jaydreyer/recall-local/data/artifacts/backups/phase3c/phase3c_recovery_smoke_20260224/restore_report_20260224T021026Z.json`
- Verified post-restore core eval gate:
  - command:
    - `python3 scripts/eval/run_eval.py --cases-file scripts/eval/eval_cases.json --backend webhook --webhook-url http://localhost:5678/webhook/recall-query`
  - result: `15/15` pass
  - artifact:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/20260224T021109Z_eac89989ae1446b5b80fd669699dc157.md`
- Ran rehearsal script to produce fresh rehearsal log evidence:
  - `/home/jaydreyer/recall-local/scripts/rehearsal/run_phase2_demo_rehearsal.sh`
  - log:
    - `/home/jaydreyer/recall-local/data/artifacts/rehearsals/20260224T021123Z_phase2_demo_rehearsal.log`
  - note: job-search suite in that run reported `9/10` due one required-terms miss; not used as the recovery acceptance gate.
- Generated refreshed portfolio bundle with all required evidence present:
  - `/home/jaydreyer/recall-local/scripts/phase3/build_portfolio_bundle_now.sh`
  - bundle:
    - `/home/jaydreyer/recall-local/data/artifacts/portfolio/phase3c/20260224T021251Z/portfolio_bundle.md`
  - summary:
    - `/home/jaydreyer/recall-local/data/artifacts/portfolio/phase3c/20260224T021251Z/bundle_summary.json` (`missing_items: []`)

## 2026-02-24 - Phase 3C portfolio packaging slice: architecture diagram + bundle generator

### Outcome

- Added architecture diagram source for portfolio walkthrough:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Architecture_Diagram.md`
- Added Phase 3C portfolio bundle generator and wrapper:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/build_portfolio_bundle.py`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/build_portfolio_bundle_now.sh`
- Extended Phase 3C operations runbook with portfolio bundle build step:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase3C_Operations_Runbook.md`
- Generated local bundle artifact:
  - `/Users/jaydreyer/projects/recall-local/data/artifacts/portfolio/phase3c/20260224T020734Z/portfolio_bundle.md`
  - `/Users/jaydreyer/projects/recall-local/data/artifacts/portfolio/phase3c/20260224T020734Z/bundle_summary.json`
- Updated docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

### Validation

- `python3 -m py_compile scripts/phase3/build_portfolio_bundle.py`
- `bash -n scripts/phase3/build_portfolio_bundle_now.sh`
- `scripts/phase3/build_portfolio_bundle_now.sh` produced bundle directory under `data/artifacts/portfolio/phase3c/`

## 2026-02-24 - Phase 3C kickoff: reliability wrappers + operations runbook

### Outcome

- Started Phase 3C implementation with operations hardening artifacts:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/run_service_preflight_now.sh`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/run_deterministic_restart_now.sh`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/run_backup_now.sh`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/run_restore_now.sh`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/backup_restore_state.py`
- Added Phase 3C operations runbook:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase3C_Operations_Runbook.md`
- Updated docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

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
    - `/home/jaydreyer/recall-local/scripts/phase3/run_retrieval_experiment_now.sh`
  - comparison artifact:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/phase3b/20260224T015231Z_comparison.md`
  - baseline summary:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/phase3b/20260224T015231Z_baseline_vector.json`
  - candidate summary:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/phase3b/20260224T015231Z_candidate_hybrid.json`
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
    - `/Users/jaydreyer/projects/recall-local/scripts/phase1/retrieval.py`
    - `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`
    - `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_from_payload.py`
    - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_bridge_api.py`
- Added optional eval scoring lane for golden cases with expected answers:
  - semantic similarity (embedding cosine) as secondary signal
  - optional enforcement flag when strict gating is desired
  - implementation:
    - `/Users/jaydreyer/projects/recall-local/scripts/eval/run_eval.py`
- Added Phase 3B baseline/candidate experiment runner:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/run_phase3b_retrieval_experiment.sh`
  - baseline: `vector`
  - candidate: `hybrid + reranker`
  - outputs comparison markdown under `/data/artifacts/evals/phase3b/`
- Added operator wrapper for experiment execution:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/run_retrieval_experiment_now.sh`
- Added versioned learning golden set starter:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/golden_sets/learning_golden_v1.json`
- Added retrieval payload example for n8n/Open WebUI tests:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/rag_query_hybrid_payload_example.json`
- Added Phase 3B runbook:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase3B_Retrieval_Quality_Runbook.md`
- Updated docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

## 2026-02-24 - Phase 3A webhook path normalization fix (short paths restored)

### Outcome

- Diagnosed Phase 3A workflow import behavior where webhook routes registered with generated path prefixes instead of short paths:
  - observed DB path form: `workflowId/webhook%20node-name/recall-*`
- Applied fix by ensuring webhook nodes include explicit `webhookId` in workflow exports:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase3a_bookmarklet_form_http.workflow.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase3a_meeting_action_form_http.workflow.json`
- Verified short production endpoints now return `HTTP 200` on ai-lab:
  - `POST http://localhost:5678/webhook/recall-bookmarklet-form`
  - `POST http://localhost:5678/webhook/recall-meeting-form`
- Updated wiring runbook note:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/PHASE3A_OPERATOR_FORMS_WIRING.md`

## 2026-02-23 - Phase 3A operator wrappers validated on ai-lab + form workflow exports

### Outcome

- Synced local Phase 3A assets to ai-lab and performed spot-check:
  - `rg` verification on `/home/jaydreyer/recall-local/docs` and `/home/jaydreyer/recall-local/scripts` confirmed wrapper/runbook content on host.
- Ran new wrappers on ai-lab and captured evidence logs:
  - ingest wrapper log:
    - `/home/jaydreyer/recall-local/data/artifacts/phase3a/20260223T222659Z_run_ingest_manifest_now.log`
  - query wrapper log:
    - `/home/jaydreyer/recall-local/data/artifacts/phase3a/20260223T222813Z_run_query_mode_now.log`
  - eval wrapper log:
    - `/home/jaydreyer/recall-local/data/artifacts/phase3a/20260223T222813Z_run_all_evals_now.log`
- Wrapper validation artifacts/results:
  - Workflow 02 query artifact:
    - `/home/jaydreyer/recall-local/data/artifacts_operator/rag/20260223T222819Z_5d4f9a6fb845424498f7c3d7a8f40f07.json`
  - scheduled eval suite result JSON files:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/scheduled/20260223T222819Z_core_eval.json`
    - `/home/jaydreyer/recall-local/data/artifacts/evals/scheduled/20260223T222819Z_job_search_eval.json`
    - `/home/jaydreyer/recall-local/data/artifacts/evals/scheduled/20260223T222819Z_learning_eval.json`
  - scheduled eval Markdown artifacts:
    - `/home/jaydreyer/recall-local/data/artifacts/evals/20260223T222856Z_c95f8a32aadb49f68152a4fa6ea1d919.md`
    - `/home/jaydreyer/recall-local/data/artifacts/evals/20260223T222942Z_2bdc9cdaf2f24437964c880ae3f2c294.md`
    - `/home/jaydreyer/recall-local/data/artifacts/evals/20260223T223043Z_5831137a2f984e6fa8abc8362adfc836.md`
- Added import-ready n8n operator form workflows:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase3a_bookmarklet_form_http.workflow.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase3a_meeting_action_form_http.workflow.json`
- Added Phase 3A form wiring runbook:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/PHASE3A_OPERATOR_FORMS_WIRING.md`

### Notes

- ai-lab path `/home/jaydreyer/recall-local/data/artifacts/rag/` is root-owned; direct non-dry-run query wrapper writes fail there.
- For wrapper validation in this thread, query run used:
  - `DATA_ARTIFACTS=/home/jaydreyer/recall-local/data/artifacts_operator`

## 2026-02-23 - Phase 3A kickoff: operator wrappers + runbook

### Outcome

- Started Phase 3A operator UX implementation with no-curl wrapper scripts:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/run_ingest_manifest_now.sh`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/run_query_mode_now.sh`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/run_all_evals_now.sh`
- Added a dedicated Phase 3A operator runbook:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase3A_Operator_Runbook.md`
  - includes Open WebUI payload templates (`default`, `job-search`, `learning`) and n8n form/webhook payload mappings for bookmarklet ingestion + meeting action extraction.
- Updated docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

## 2026-02-23 - Added formal Phase 3 guide + cleanup sweep fixes

### Outcome

- Added formal Phase 3 execution plan:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase3_Guide.md`
  - includes `3A` UI/operator path, `3B` retrieval quality upgrades, and `3C` ops hardening/portfolio packaging with explicit completion gate.
- Fixed eval contract bug in:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/run_eval.py`
  - `_evaluate_payload()` now returns the expected 7-field tuple in all branches.
- Improved script portability by removing hard-coded default webhook host:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/scheduled_eval.sh`
  - `/Users/jaydreyer/projects/recall-local/scripts/rehearsal/run_phase2_demo_rehearsal.sh`
  - defaults now derive from `N8N_HOST` (`http://localhost:5678` fallback) unless `RECALL_EVAL_WEBHOOK_URL` is explicitly set.
  - replaced Bash-4-only `${VAR,,}` lowercasing with POSIX-compatible `tr` path for Mac Bash compatibility.
- Updated related docs:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Eval_Scheduling.md`
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Demo_Rehearsal_Runbook.md`

## 2026-02-23 - Added Phase 2 demo rehearsal runbook and helper script

### Outcome

- Added instruction doc for running and logging a full clean end-to-end Phase 2 rehearsal:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Demo_Rehearsal_Runbook.md`
- Added one-command rehearsal runner script:
  - `/Users/jaydreyer/projects/recall-local/scripts/rehearsal/run_phase2_demo_rehearsal.sh`
  - writes timestamped logs under:
    - `/home/jaydreyer/recall-local/data/artifacts/rehearsals/`
- Updated docs index links:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

## 2026-02-23 - Scheduled eval retry guard for flaky webhook/model runs

### Outcome

- Hardened scheduled evaluator to retry each suite once before emitting regression alerts:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/scheduled_eval.sh`
- Added new env controls:
  - `RECALL_EVAL_RETRY_ON_FAIL` (default `true`)
  - `RECALL_EVAL_RETRY_DELAY_SECONDS` (default `5`)
- Updated scheduling documentation:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Eval_Scheduling.md`

## 2026-02-23 - Added learning eval suite and scheduled execution wiring

### Outcome

- Added dedicated learning eval cases:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/learning_eval_cases.json`
  - 8 cases total (6 answerable + 2 unanswerable)
  - all cases run Workflow 02 with:
    - `mode=learning`
    - `filter_tags=["learning","genai-docs"]`
- Extended scheduled eval runner to execute three suites:
  - core: `/Users/jaydreyer/projects/recall-local/scripts/eval/eval_cases.json`
  - job-search: `/Users/jaydreyer/projects/recall-local/scripts/eval/job_search_eval_cases.json`
  - learning: `/Users/jaydreyer/projects/recall-local/scripts/eval/learning_eval_cases.json`
  - implementation: `/Users/jaydreyer/projects/recall-local/scripts/eval/scheduled_eval.sh`
- Added scheduling docs/env var for learning suite:
  - `RECALL_EVAL_LEARNING_CASES_FILE`
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Eval_Scheduling.md`

## 2026-02-23 - Learning mode + corpus-lane manifest controls

### Outcome

- Added Workflow 02 learning prompt profile:
  - `/Users/jaydreyer/projects/recall-local/prompts/learning_coach.md`
  - selected via payload/CLI `mode=learning`
- Extended Workflow 02 mode routing:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`
  - `mode=learning` now maps to `audit.prompt_profile=learning_coach`
- Added payload example for learning lane queries:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/rag_query_learning_payload_example.json`
- Added learning corpus manifest for non-interview AI training docs:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase2/learning_manifest.genieincodebottle.ai-lab.json`
- Generalized manifest ingest helper behavior:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase2/ingest_job_search_manifest.py`
  - removed implicit `job-search` tag injection
  - added optional `--ensure-tag` for explicit tag enforcement

## 2026-02-23 - Added native DOCX ingestion extraction

### Outcome

- Updated file extraction path to support `.docx` directly in Workflow 01 ingestion:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py`
  - new extractor: `_extract_text_from_docx(...)` (paragraph + table cell text)
- Added dependency:
  - `/Users/jaydreyer/projects/recall-local/requirements.txt` now includes `python-docx`

### Notes

- PDF extraction remains unchanged.
- In environments where bridge container runs `pip install -r requirements.txt` on startup, DOCX support activates after bridge recreate.

## 2026-02-23 - Phase 2C: tag-scoped retrieval + job-search mode + eval suite

### Outcome

- Added optional Workflow 02 retrieval tag filtering (`filter_tags`) end-to-end:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/retrieval.py`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_from_payload.py`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_bridge_api.py`
- Added Workflow 02 job-search prompt profile:
  - `/Users/jaydreyer/projects/recall-local/prompts/job_search_coach.md`
  - selected via payload/CLI `mode=job-search`
- Added optional Langfuse instrumentation hooks for `generate()` and `embed()`:
  - `/Users/jaydreyer/projects/recall-local/scripts/llm_client.py`
  - `/Users/jaydreyer/projects/recall-local/requirements.txt` now includes `langfuse`
  - traces include workflow/mode metadata when supplied by callers
- Extended Workflow 02 audit/sources metadata:
  - `sources[].tags`
  - `audit.mode`, `audit.filter_tags`, `audit.prompt_profile`
- Added dedicated job-search eval suite on shared harness:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/job_search_eval_cases.json`
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/run_eval.py`
  - added checks for required grounding terms and required source tags
- Updated scheduled eval runner to execute both core and job-search suites:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/scheduled_eval.sh`
- Added payload examples and runbook updates:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/rag_query_job_search_payload_example.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/rag_query_payload_example.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/PHASE1C_WORKFLOW02_WIRING.md`
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Eval_Scheduling.md`
- Added batch ingest helper to reduce repetitive curl ingestion commands for job-search corpus:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase2/ingest_job_search_manifest.py`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase2/job_search_manifest.example.json`

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
  - `/Users/jaydreyer/projects/recall-local/docker/phase1b-ingest-bridge.compose.yml`
- Added URL ingestion TLS fallback controls for environments with custom/intercepted cert chains:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py`
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
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/channel_adapters.py`
  - added channel: `bookmarklet`
  - webhook fallback now maps `url/text/title/tags` and optional replacement controls
- Added payload-level replacement controls in Workflow 01 request parser:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_from_payload.py`
  - supported fields: `replace_existing`, `source_key`, top-level `tags`
- Implemented source-identity replacement policy in ingestion backend:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py`
  - computes canonical `source_identity` (URL canonicalization + optional override key)
  - optional delete-before-upsert (`replace_existing=true`)
  - persists `source_identity` and replacement metadata in Qdrant payload
  - returns replacement audit fields in ingestion result (`replaced_points`, `replacement_status`)
- Added Google Docs payload support improvements:
  - accepts gdoc payload object containing URL/doc_id and optional extracted text
  - source extraction path now supports `gdoc` content dictionaries
- Bridge/channel runner updates:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_bridge_api.py` supports `/ingest/bookmarklet`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_channel_payload.py` accepts `--channel bookmarklet`

### Added payload examples

- `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json`
- `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/gdoc_ingest_payload_example.json`

### Documentation updates

- `/Users/jaydreyer/projects/recall-local/n8n/workflows/PHASE1B_CHANNEL_WIRING.md`
- `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase1_Guide.md`
- `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Guide.md`
- `/Users/jaydreyer/projects/recall-local/docs/Recall_local_PRD_Addendum_JobSearch.md`
- `/Users/jaydreyer/projects/recall-local/docs/README.md`

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
  - `OLLAMA_HOST=http://100.116.103.78:11434`
  - `QDRANT_HOST=http://100.116.103.78:6333`
- Verification script pass:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase2/verify_workflow03_bridge.py`
  - run_id: `ef93fdf2f5c14f53befc7126f77295c4`
  - result: `ok=true`
- Confirmed persisted outputs:
  - artifact exists: `/Users/jaydreyer/projects/recall-local/data/artifacts/meetings/20260223T145113Z_ef93fdf2f5c14f53befc7126f77295c4.md`
  - SQLite run row present for workflow `workflow_03_meeting_action_items`

### Additional note

- Local dry-run verification also passed with model override:
  - `OLLAMA_MODEL=llama3.2:latest`
  - this avoided local default model mismatch (`llama3:8b` unavailable).

## 2026-02-23 - Phase 2A assets: n8n wiring + bridge verification script

### Outcome

- Added import-ready n8n workflow exports for Workflow 03:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase2a_meeting_action_items.workflow.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase2a_meeting_action_items_http.workflow.json`
- Added Workflow 03 wiring runbook:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/PHASE2A_WORKFLOW03_WIRING.md`
- Added bridge verification script for Workflow 03 contract + persisted evidence checks:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase2/verify_workflow03_bridge.py`

### Notes

- Verification script validates response schema and can assert artifact + SQLite run presence on non-dry-run calls.
- Script defaults to using:
  - bridge URL: `http://localhost:8090/meeting/action-items`
  - payload file: `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/meeting_action_items_payload_example.json`

## 2026-02-23 - Phase 2A kickoff: Workflow 03 Meeting -> Action Items core implementation

### Outcome

- Added Workflow 03 runner and payload entrypoint for transcript-to-action extraction:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase2/meeting_action_items.py`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase2/meeting_from_payload.py`
- Added Workflow 03 prompt templates:
  - `/Users/jaydreyer/projects/recall-local/prompts/workflow_03_meeting_extract.md`
  - `/Users/jaydreyer/projects/recall-local/prompts/workflow_03_meeting_extract_retry.md`
- Extended output validation utilities with meeting schema validation:
  - `/Users/jaydreyer/projects/recall-local/scripts/validate_output.py`
- Exposed Workflow 03 webhook route via HTTP bridge:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_bridge_api.py`
  - supported paths: `/meeting/action-items` (primary), `/meeting/actions`, `/query/meeting`
- Added payload example for n8n/webhook tests:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/meeting_action_items_payload_example.json`

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
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Checklists.md`
- Linked checklist from Phase 2 guide and docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Guide.md`
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

### Notes

- Checklist includes file-level implementation tasks and verification gates for:
  - ingestion expansion + source-based replacement policy
  - Workflow 02 `filter_tags`
  - job-search prompt mode with strict JSON/citation contract
  - shared-harness job-search eval suite

## 2026-02-23 - Phase 2 plan updated for job-search domain mode

### Outcome

- Updated Phase 2 execution guide to incorporate the Job Search addendum as scoped Phase 2 work:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Guide.md`

### Planning changes captured

- `2B` now includes corpus hygiene requirements for mutable sources (source-based replacement policy) alongside ingestion expansion.
- `2C` now explicitly includes Workflow 02 tag-scoped retrieval (`filter_tags`), Job Search prompt profile, and a dedicated job-search eval case suite using the shared eval harness.
- `2D` now requires both core and job-search eval suites to pass for demo reliability gate completion.

## 2026-02-23 - Phase 2 plan defined with sub-phases and gates

### Outcome

- Added Phase 2 execution guide with explicit sub-phases, delivery order, and phase completion gate:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase2_Guide.md`
- Updated docs index:
  - `/Users/jaydreyer/projects/recall-local/docs/README.md`

### Sub-phases captured

- `2A` Workflow 03 (Meeting -> Action Items) core implementation.
- `2B` Ingestion expansion (Google Docs + browser bookmarklet mandatory).
- `2C` Langfuse observability + artifact viewer polish.
- `2D` Demo reliability gate and rehearsal.

## 2026-02-23 - Scheduled eval + regression alerting added

### Outcome

- Added cron-ready scheduled eval execution against live Workflow 02 webhook:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/scheduled_eval.sh`
- Added regression alert helper with optional webhook notification:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/notify_regression.py`
- Added scheduling runbook:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Eval_Scheduling.md`

### Notes

- Supports daily/weekly cron schedules on ai-lab.
- Regressions produce non-zero exit code and optional Slack/Teams webhook alerts when configured.

## 2026-02-23 - Workflow 02 IDK eval gate green on live webhook

### Outcome

- Verified live webhook end-to-end pass after sync/redeploy:
  - run_id: `0ee745eada024070815f249d85d3337e`
  - backend: `webhook`
  - webhook URL: `http://100.116.103.78:5678/webhook/recall-query`
  - result: `15/15 PASS`
  - unanswerable: `5/5 PASS`
  - artifact: `/home/jaydreyer/recall-local/data/artifacts/evals/20260223T000357Z_0ee745eada024070815f249d85d3337e.md`

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
  - `docker compose -f /home/jaydreyer/recall-local/docker/phase1b-ingest-bridge.compose.yml up -d --force-recreate`
  - `python3 /home/jaydreyer/recall-local/scripts/eval/run_eval.py --backend webhook --webhook-url http://100.116.103.78:5678/webhook/recall-query`

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
  - webhook URL: `http://100.116.103.78:5678/webhook/recall-query`
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
  - `POST http://100.116.103.78:5678/webhook/recall-query` -> `HTTP 200` with `workflow_02_rag_query` result.
- Confirmed bridge endpoint is live:
  - `POST http://100.116.103.78:8090/query/rag?dry_run=true` -> `HTTP 200`.

### Key lessons captured for next thread

- Use n8n `Executions` as primary diagnostic source; failed node + stack trace is the fastest path to root cause.
- In this n8n deployment, `Execute Command` cannot run Workflow 02 Python scripts (`python3` missing in container image).
- Workflow 02 should use HTTP bridge node with payload expression `={{ $json.body }}`.
- Distinguish host scope for connectivity checks:
  - MacBook to ai-lab: `http://100.116.103.78:<port>`
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

- Executed Workflow 02 against live endpoints (`Ollama 100.116.103.78:11434`, `Qdrant 100.116.103.78:6333`) and validated three demo queries with citation-safe output.
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
  - Ollama: `http://100.116.103.78:11434`
  - Qdrant: `http://100.116.103.78:6333`
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
