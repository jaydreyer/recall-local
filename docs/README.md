# Recall.local Documentation Index

This folder is the source of truth for what has been planned, implemented, and currently running.

## Core Documents

- `Recall_local_PRD.md`: Product requirements and architecture intent.
- `Recall_local_Phase0_Guide.md`: Phase 0 implementation instructions.
- `Recall_local_Phase1_Guide.md`: Phase 1 kickoff implementation and runbook.
- `Recall_local_Phase1D_Eval_Guide.md`: Eval harness runbook and troubleshooting protocol.
- `Recall_local_Phase2_Guide.md`: Phase 2 sub-phases, execution order, and completion gate.
- `Recall_local_Phase3_Guide.md`: Formal post-Phase-2 plan (UI-first operation, retrieval quality upgrades, and ops hardening).
- `Recall_local_Phase3_Completion_Summary.md`: Phase 3 completion outcomes, evidence pointers, and residual follow-up.
- `Recall_local_Phase4_Guide.md`: Phase 4 execution plan for reliability telemetry, CI/release guardrails, and maintenance hygiene.
- `Recall_local_Phase5_Guide.md`: Phase 5 execution plan for dashboard UI, Chrome extension, Obsidian integration, and final hardening.
- `Recall_local_Phase5_Checklists.md`: Actionable implementation checklist for Phase 5 workstreams and completion gate.
- `phase5-punch-list.md`: Post-audit punch list for Phase 5 completion gaps and polish items.
- `Recall_local_Phase5_Operator_Entrypoint_Runbook.md`: Single compose/runtime entrypoint runbook for Phase 5 hardening operations.
- `Recall_local_Phase5_Demo_Runbook.md`: One-command Phase 5 demo runbook covering dashboard, extension, vault, and eval lanes.
- `phase5-implementation-brief.md`: Architecture review brief and recommendation source for Phase 5 planning decisions.
- `scaffolds/recall-dashboard.jsx`: Dashboard UI concept scaffold used as implementation reference.
- `scaffolds/recall-chrome-popup.jsx`: Chrome popup UX concept scaffold used as implementation reference.
- `Recall_local_Release_Checklist.md`: Release preflight, tag convention, push sequence, and rollback flow for Phase 4 cadence.
- `Recall_local_Phase3A_Operator_Runbook.md`: Operator-first runbook for no-curl ingestion/query/eval paths and UI payload templates.
- `Recall_local_Phase3B_Retrieval_Quality_Runbook.md`: Hybrid/reranker retrieval controls, eval scoring lane, and baseline/candidate experiment runbook.
- `Recall_local_Phase3C_Operations_Runbook.md`: Deterministic restart, service preflight, and backup/restore runbook for ops hardening.
- `Recall_local_Architecture_Diagram.md`: Mermaid architecture diagram for walkthrough and portfolio evidence.
- `Recall_local_Phase2_Checklists.md`: Actionable implementation checklist for Phase 2 (`2B` and `2C`) including job-search domain mode tasks.
- `Recall_local_Phase2_Demo_Rehearsal_Runbook.md`: One-command and manual script for logging a full clean Phase 2 rehearsal.
- `Recall_local_RAG_Tuning_Playbook.md`: System-level RAG tuning summary (ingestion, retrieval, prompts, guardrails, reliability, evals).
- `Recall_local_Eval_Scheduling.md`: Daily/weekly eval scheduling and regression alert setup.
- `../n8n/workflows/payload_examples/meeting_action_items_payload_example.json`: Sample payload for Workflow 03 (`2A`) webhook testing.
- `../n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json`: Sample payload for bookmarklet ingestion with source-based replacement.
- `../n8n/workflows/payload_examples/gdoc_ingest_payload_example.json`: Sample payload for Google Docs ingestion with source-based replacement.
- `../n8n/workflows/payload_examples/rag_query_job_search_payload_example.json`: Sample Workflow 02 payload for `mode=job-search` with `filter_tags`.
- `../n8n/workflows/payload_examples/rag_query_learning_payload_example.json`: Sample Workflow 02 payload for `mode=learning` with learning-focused `filter_tags`.
- `../n8n/workflows/payload_examples/rag_query_hybrid_payload_example.json`: Sample Workflow 02 payload using Phase 3B `hybrid` retrieval + reranker options.
- `../scripts/eval/job_search_eval_cases.json`: Dedicated job-search eval suite for shared eval harness.
- `../scripts/eval/learning_eval_cases.json`: Dedicated learning-mode eval suite for shared eval harness.
- `../prompts/job_search_coach.md`: Workflow 02 job-search prompt profile used by `mode=job-search`.
- `../prompts/learning_coach.md`: Workflow 02 learning prompt profile used by `mode=learning`.
- `../scripts/phase2/ingest_job_search_manifest.py`: Batch ingest runner for job-search corpus from one manifest file.
- `../scripts/phase2/job_search_manifest.example.json`: Starter manifest template for batch job-search ingestion.
- `../scripts/phase2/learning_manifest.genieincodebottle.ai-lab.json`: Learning-lane manifest for non-interview AI training corpus.
- `../scripts/rehearsal/run_phase2_demo_rehearsal.sh`: Automated Phase 2 rehearsal runner with timestamped log output.
- `../scripts/phase3/run_ingest_manifest_now.sh`: Phase 3A one-command manifest ingestion wrapper.
- `../scripts/phase3/run_query_mode_now.sh`: Phase 3A one-command query-mode wrapper (`default`, `job-search`, `learning`).
- `../scripts/phase3/run_all_evals_now.sh`: Phase 3A one-command wrapper for all eval suites.
- `../scripts/phase3/run_retrieval_experiment_now.sh`: Phase 3B one-command baseline vs candidate retrieval experiment wrapper.
- `../scripts/phase3/run_service_preflight_now.sh`: Phase 3C one-command preflight checks (connectivity, bridge, webhook dry-run).
- `../scripts/phase3/run_deterministic_restart_now.sh`: Phase 3C deterministic service restart with health waits.
- `../scripts/phase3/run_backup_now.sh`: Phase 3C backup wrapper for SQLite + Qdrant export.
- `../scripts/phase3/run_restore_now.sh`: Phase 3C restore wrapper (latest or explicit backup folder).
- `../scripts/phase3/backup_restore_state.py`: Shared Phase 3C backup/restore utility used by wrappers.
- `../scripts/phase3/build_portfolio_bundle_now.sh`: Phase 3C portfolio bundle wrapper that assembles evidence pack from artifacts.
- `../scripts/phase3/build_portfolio_bundle.py`: Phase 3C portfolio bundle generator (trend snapshot + evidence copy + summary).
- `../scripts/phase4/run_eval_soak_now.sh`: Phase 4A soak wrapper for repeated core/job-search eval runs plus thresholded trend summary output.
- `../scripts/phase4/summarize_eval_trend.py`: Phase 4A trend aggregator that emits pass-rate/latency/failure-histogram JSON + Markdown artifacts.
- `../scripts/phase4/run_repo_hygiene_check.sh`: Phase 4C hygiene checker for `._*` metadata files, ai-lab dirty repo state, and stale stashes.
- `../scripts/phase5/vault_sync.py`: Phase 5C Obsidian vault sync runtime (`--once` hash dedupe + `--watch` debounce mode with Syncthing-aware move handling).
- `../scripts/phase5/run_vault_sync_now.sh`: Phase 5C one-command wrapper for one-shot vault sync.
- `../scripts/phase5/run_vault_watch_now.sh`: Phase 5C one-command wrapper for continuous vault watch mode.
- `../scripts/phase5/run_operator_stack_now.sh`: Phase 5F one-command compose/runtime entrypoint (up/down/restart/status/logs/preflight/config).
- `../scripts/phase5/run_phase5_demo_now.sh`: Phase 5F one-command demo runner (dashboard ingest/query, extension gate, vault sync/query, eval gate).
- `../n8n/workflows/phase6/README.md`: Phase 6B guided build index for job discovery workflows.
- `../n8n/workflows/phase6/workflow1_aggregator.md`: Step-by-step Workflow 1 n8n build notes (aggregator discovery).
- `../n8n/workflows/phase6/workflow2_career_pages.md`: Step-by-step Workflow 2 n8n build notes (career page monitoring).
- `../n8n/workflows/phase6/workflow3_evaluate_notify.md`: Step-by-step Workflow 3 n8n evaluate/notify build notes (full Phase 6C flow).
- `../n8n/workflows/phase6b_career_page_monitor_import.workflow.json`: Import-ready Workflow 2 n8n automation for career-page monitoring via bridge APIs.
- `../n8n/workflows/phase6b_career_page_monitor_traditional_import.workflow.json`: Import-ready traditional multi-node Workflow 2 n8n automation (step-level debugging visibility).
- `../ui/dashboard/`: Phase 5D React/Vite dashboard app (Ingest, Query, Activity, Eval, Vault) with bridge API settings.
- `../ui/dashboard/Dockerfile`: Phase 5D dashboard container build for `recall-ui`.
- `../chrome-extension/`: Phase 5E/5E.1 Chrome extension implementation (Manifest V3 popup, context menu capture, shortcut command, settings page, Gmail content script prefill).
- `../scripts/eval/run_phase3b_retrieval_experiment.sh`: Phase 3B retrieval experiment runner (`vector` baseline vs `hybrid+rereank` candidate).
- `../scripts/eval/golden_sets/learning_golden_v1.json`: Versioned learning golden set with optional semantic-score references.
- `../n8n/workflows/phase3a_bookmarklet_form_http.workflow.json`: Import-ready n8n bookmarklet-form workflow for bridge ingestion.
- `../n8n/workflows/phase3a_meeting_action_form_http.workflow.json`: Import-ready n8n meeting-form workflow for Workflow 03 bridge route.

## Operational Documentation

- `IMPLEMENTATION_LOG.md`: Chronological record of what was changed, when, and why.
- `ENVIRONMENT_INVENTORY.md`: Current state snapshot (services, ports, models, setup decisions).
- `CONTEXT_KICKOFF_SHARING_GUIDE.md`: Shareable guide for adopting the context-kickoff pattern across projects.
- `../n8n/workflows/PHASE1C_WORKFLOW02_WIRING.md`: Workflow 02 deployment and troubleshooting runbook.
- `../n8n/workflows/PHASE2A_WORKFLOW03_WIRING.md`: Workflow 03 deployment and troubleshooting runbook.
- `../n8n/workflows/PHASE3A_OPERATOR_FORMS_WIRING.md`: Phase 3A operator webhook/form import and smoke-test runbook.
- `../scripts/phase2/verify_workflow03_bridge.py`: Workflow 03 bridge verification helper (contract + persisted evidence checks).
- `../.github/workflows/quality_checks.yml`: Phase 4B CI gate for syntax checks and wrapper smoke help checks.

## Shareable Kit

- `context-kickoff-kit/`: Public-ready starter package containing a sanitized `context-kickoff` skill folder and install notes.

## Documentation Policy

For every meaningful setup or implementation change:

1. Add a new dated entry in `IMPLEMENTATION_LOG.md`.
2. Update `ENVIRONMENT_INVENTORY.md` if the live state changed.
3. Include exact file paths, hostnames, ports, and commands where useful.
