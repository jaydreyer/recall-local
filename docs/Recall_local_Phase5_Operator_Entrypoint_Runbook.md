# Recall.local - Phase 5 Operator Entrypoint Runbook

Purpose: provide a single compose/runtime entrypoint for operator usage during Phase `5F`.

Entrypoint script:
- `/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh`

Consolidated compose files used by this entrypoint:
- `/Users/jaydreyer/projects/recall-local/docker/phase1b-ingest-bridge.compose.yml`
- `/Users/jaydreyer/projects/recall-local/docker/docker-compose.yml`

## Commands

Show help:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh help
```

Start stack:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh up
```

Start stack with forced recreate and preflight:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh up --recreate --preflight
```

Restart stack:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh restart
```

Show status:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh status
```

Tail logs:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh logs
```

Tail logs for one service:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh logs recall-ingest-bridge
```

Run preflight only:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh preflight
```

Print effective compose services:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh config
```

Stop stack:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_operator_stack_now.sh down
```

## Notes

- `up --preflight` and `restart --preflight` call:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase3/run_service_preflight_now.sh`
- Preflight URL overrides are supported:
  - `--bridge-url`
  - `--n8n-host`
- This runbook does not replace deterministic restart and backup/restore runbooks from Phase `3C`; it provides a single operator entrypoint for compose/runtime actions in Phase `5F`.
