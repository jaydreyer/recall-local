# Recall.local Documentation Index

This folder is the source of truth for what has been planned, implemented, and currently running.

## Core Documents

- `Recall_local_PRD.md`: Product requirements and architecture intent.
- `Recall_local_Phase0_Guide.md`: Phase 0 implementation instructions.
- `Recall_local_Phase1_Guide.md`: Phase 1 kickoff implementation and runbook.
- `Recall_local_Phase1D_Eval_Guide.md`: Eval harness runbook and troubleshooting protocol.
- `Recall_local_Phase2_Guide.md`: Phase 2 sub-phases, execution order, and completion gate.
- `Recall_local_Phase2_Checklists.md`: Actionable implementation checklist for Phase 2 (`2B` and `2C`) including job-search domain mode tasks.
- `Recall_local_RAG_Tuning_Playbook.md`: System-level RAG tuning summary (ingestion, retrieval, prompts, guardrails, reliability, evals).
- `Recall_local_Eval_Scheduling.md`: Daily/weekly eval scheduling and regression alert setup.
- `../n8n/workflows/payload_examples/meeting_action_items_payload_example.json`: Sample payload for Workflow 03 (`2A`) webhook testing.
- `../n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json`: Sample payload for bookmarklet ingestion with source-based replacement.
- `../n8n/workflows/payload_examples/gdoc_ingest_payload_example.json`: Sample payload for Google Docs ingestion with source-based replacement.
- `../n8n/workflows/payload_examples/rag_query_job_search_payload_example.json`: Sample Workflow 02 payload for `mode=job-search` with `filter_tags`.
- `../n8n/workflows/payload_examples/rag_query_learning_payload_example.json`: Sample Workflow 02 payload for `mode=learning` with learning-focused `filter_tags`.
- `../scripts/eval/job_search_eval_cases.json`: Dedicated job-search eval suite for shared eval harness.
- `../scripts/eval/learning_eval_cases.json`: Dedicated learning-mode eval suite for shared eval harness.
- `../prompts/job_search_coach.md`: Workflow 02 job-search prompt profile used by `mode=job-search`.
- `../prompts/learning_coach.md`: Workflow 02 learning prompt profile used by `mode=learning`.
- `../scripts/phase2/ingest_job_search_manifest.py`: Batch ingest runner for job-search corpus from one manifest file.
- `../scripts/phase2/job_search_manifest.example.json`: Starter manifest template for batch job-search ingestion.
- `../scripts/phase2/learning_manifest.genieincodebottle.ai-lab.json`: Learning-lane manifest for non-interview AI training corpus.

## Operational Documentation

- `IMPLEMENTATION_LOG.md`: Chronological record of what was changed, when, and why.
- `ENVIRONMENT_INVENTORY.md`: Current state snapshot (services, ports, models, setup decisions).
- `CONTEXT_KICKOFF_SHARING_GUIDE.md`: Shareable guide for adopting the context-kickoff pattern across projects.
- `../n8n/workflows/PHASE1C_WORKFLOW02_WIRING.md`: Workflow 02 deployment and troubleshooting runbook.
- `../n8n/workflows/PHASE2A_WORKFLOW03_WIRING.md`: Workflow 03 deployment and troubleshooting runbook.
- `../scripts/phase2/verify_workflow03_bridge.py`: Workflow 03 bridge verification helper (contract + persisted evidence checks).

## Shareable Kit

- `context-kickoff-kit/`: Public-ready starter package containing a sanitized `context-kickoff` skill folder and install notes.

## Documentation Policy

For every meaningful setup or implementation change:

1. Add a new dated entry in `IMPLEMENTATION_LOG.md`.
2. Update `ENVIRONMENT_INVENTORY.md` if the live state changed.
3. Include exact file paths, hostnames, ports, and commands where useful.
