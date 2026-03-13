# Recall.local - Phase 5 Operator Entrypoint Runbook

Purpose: provide a single compose/runtime entrypoint for operator usage during Phase `5F`.

Entrypoint script:
- `<repo-root>/scripts/phase5/run_operator_stack_now.sh`

Default compose mode (`full`):
- `<repo-root>/docker/docker-compose.yml`

Lite compose mode (`--lite`, Approach B for pre-existing services):
- `<repo-root>/docker/phase1b-ingest-bridge.compose.yml`
- `<repo-root>/docker/docker-compose.lite.yml`

## Commands

Show help:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh help
```

Start stack:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh up
```

Start stack in lite mode:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh up --lite
```

Start stack with forced recreate and preflight:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh up --recreate --preflight
```

Restart stack:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh restart
```

Show status:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh status
```

Tail logs:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh logs
```

Tail logs for one service:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh logs recall-ingest-bridge
```

Run preflight only:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh preflight
```

Print effective compose services:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh config
```

Print effective compose services in lite mode:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh config --lite
```

Stop stack:

```bash
<repo-root>/scripts/phase5/run_operator_stack_now.sh down
```

## Notes

- `up --preflight` and `restart --preflight` call:
  - `<repo-root>/scripts/phase3/run_service_preflight_now.sh`
- Preflight URL overrides are supported:
  - `--bridge-url`
  - `--n8n-host`
- Compose mode override:
  - `--lite` for Approach B services while keeping externally managed core runtimes.
- This runbook does not replace deterministic restart and backup/restore runbooks from Phase `3C`; it provides a single operator entrypoint for compose/runtime actions in Phase `5F`.
