# Recall.local - Phase 5 Demo Runbook

Purpose: run a single Phase `5F` demo script that records evidence for all required demo lanes.

Entrypoint script:
- `/Users/jaydreyer/projects/recall-local/scripts/phase5/run_phase5_demo_now.sh`

Covered lanes:
1. dashboard ingest/query
2. extension capture gate
3. Obsidian sync/query
4. eval gate check

## Commands

Show help:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_phase5_demo_now.sh --help
```

Dry-run mode (default):

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_phase5_demo_now.sh
```

Dry-run mode against ai-lab bridge:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_phase5_demo_now.sh \
  --bridge-url http://100.116.103.78:8090 \
  --mode dry-run \
  --eval-suite both
```

Live mode with API key and strict eval pass requirement:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_phase5_demo_now.sh \
  --mode live \
  --api-key "$RECALL_API_KEY" \
  --eval-suite both \
  --require-eval-pass
```

Enable Gmail browser smoke harness in extension lane:

```bash
/Users/jaydreyer/projects/recall-local/scripts/phase5/run_phase5_demo_now.sh \
  --run-extension-browser-smoke
```

## Outputs

- Artifacts are written to:
  - `data/artifacts/demos/phase5/<timestamp>/`
- Key outputs per run:
  - `phase5_demo.log`
  - request/response JSON for each lane
  - `phase5_demo_summary.json`
  - extension lane logs (`extension_unittest.log`, optional browser smoke artifacts)

## Notes

- `--mode dry-run` is default for deterministic script rehearsal.
- `--mode live` sends non-dry-run requests for ingestion/query/vault/eval lanes.
- If `RECALL_API_KEY` is configured on bridge, pass the same key via `--api-key` (or `RECALL_API_KEY` env).
- Browser smoke is optional because it requires Playwright runtime plus UI-capable environment.
