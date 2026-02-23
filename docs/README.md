# Recall.local Documentation Index

This folder is the source of truth for what has been planned, implemented, and currently running.

## Core Documents

- `Recall_local_PRD.md`: Product requirements and architecture intent.
- `Recall_local_Phase0_Guide.md`: Phase 0 implementation instructions.
- `Recall_local_Phase1_Guide.md`: Phase 1 kickoff implementation and runbook.
- `Recall_local_Phase1D_Eval_Guide.md`: Eval harness runbook and troubleshooting protocol.
- `Recall_local_Phase2_Guide.md`: Phase 2 sub-phases, execution order, and completion gate.
- `Recall_local_Eval_Scheduling.md`: Daily/weekly eval scheduling and regression alert setup.

## Operational Documentation

- `IMPLEMENTATION_LOG.md`: Chronological record of what was changed, when, and why.
- `ENVIRONMENT_INVENTORY.md`: Current state snapshot (services, ports, models, setup decisions).
- `CONTEXT_KICKOFF_SHARING_GUIDE.md`: Shareable guide for adopting the context-kickoff pattern across projects.
- `../n8n/workflows/PHASE1C_WORKFLOW02_WIRING.md`: Workflow 02 deployment and troubleshooting runbook.

## Shareable Kit

- `context-kickoff-kit/`: Public-ready starter package containing a sanitized `context-kickoff` skill folder and install notes.

## Documentation Policy

For every meaningful setup or implementation change:

1. Add a new dated entry in `IMPLEMENTATION_LOG.md`.
2. Update `ENVIRONMENT_INVENTORY.md` if the live state changed.
3. Include exact file paths, hostnames, ports, and commands where useful.
