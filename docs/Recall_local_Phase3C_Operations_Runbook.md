# Recall.local - Phase 3C Operations Runbook

Purpose: provide deterministic restart, preflight, and backup/restore procedures for ai-lab operations hardening.

## What shipped in this slice

1. Service preflight wrapper:
   - `<repo-root>/scripts/phase3/run_service_preflight_now.sh`
2. Deterministic restart wrapper:
   - `<repo-root>/scripts/phase3/run_deterministic_restart_now.sh`
3. Backup wrapper (SQLite + Qdrant export):
   - `<repo-root>/scripts/phase3/run_backup_now.sh`
4. Daily full-backup wrapper:
   - `<repo-root>/scripts/phase3/run_daily_full_backup.sh`
5. Restore wrapper:
   - `<repo-root>/scripts/phase3/run_restore_now.sh`
6. Shared backup/restore utility:
   - `<repo-root>/scripts/phase3/backup_restore_state.py`
7. Portfolio bundle builder:
   - `<repo-root>/scripts/phase3/build_portfolio_bundle_now.sh`
   - `<repo-root>/scripts/phase3/build_portfolio_bundle.py`

## Important sync rule (Mac -> ai-lab)

Before any ai-lab restart or validation run, sync local changes to `<server-repo-root>` and spot-check remote content.

Quick spot-check example after sync:

```bash
ssh jaydreyer@<ai-lab-tailnet-ip> \
  'rg -n "run_deterministic_restart_now|backup_restore_state" <server-repo-root>/scripts/phase3'
```

## Cold-start to demo flow

Run these on ai-lab from `<server-repo-root>`.

1. Deterministic restart + post-restart preflight:

```bash
<server-repo-root>/scripts/phase3/run_deterministic_restart_now.sh
```

2. One ingest operation:

```bash
<server-repo-root>/scripts/phase3/run_ingest_manifest_now.sh --profile learning
```

3. One query operation:

```bash
<server-repo-root>/scripts/phase3/run_query_mode_now.sh --mode learning
```

4. One eval pass:

```bash
python3 <server-repo-root>/scripts/eval/run_eval.py \
  --cases-file <server-repo-root>/scripts/eval/eval_cases.json \
  --backend webhook \
  --webhook-url http://localhost:5678/webhook/recall-query
```

## Backup snapshot

Default output root:

- `<server-repo-root>/data/artifacts/backups/phase3c/`

Create backup:

```bash
<server-repo-root>/scripts/phase3/run_backup_now.sh
```

Optional named backup:

```bash
<server-repo-root>/scripts/phase3/run_backup_now.sh --backup-name before_recovery_smoke
```

Each backup contains:

1. `sqlite/recall.db`
2. `qdrant/points.jsonl`
3. `manifest.json`

## Daily full backup snapshot

Default output root:

- `<server-repo-root>/data/artifacts/backups/daily_full/`

Run on demand:

```bash
<server-repo-root>/scripts/phase3/run_daily_full_backup.sh
```

Daily ai-lab cron schedule:

```cron
CRON_TZ=America/Chicago
15 2 * * * cd <server-repo-root> && PYTHON_BIN=<server-repo-root>/.venv/bin/python /bin/bash scripts/phase3/run_daily_full_backup.sh >> <server-repo-root>/data/artifacts/backups/daily_full/cron.log 2>&1
```

Coverage:

1. logical SQLite + all-Qdrant export under `state/`
2. consistent `n8n` SQLite snapshot (`runtime/n8n-database.sqlite`)
3. archived `n8n` runtime directory excluding the live SQLite files
4. archived `data/` tree excluding nested backup folders
5. raw `recall_qdrant-storage` Docker volume tarball
6. compose/env config bundle plus git revision snapshot

Retention:

- default `14` days via `RECALL_DAILY_BACKUP_RETENTION_DAYS`
- current backup is also linked at `<server-repo-root>/data/artifacts/backups/daily_full/latest`

## Restore snapshot

Restore latest backup:

```bash
<server-repo-root>/scripts/phase3/run_restore_now.sh
```

Restore specific backup and rebuild collection first:

```bash
<server-repo-root>/scripts/phase3/run_restore_now.sh \
  --backup-dir <server-repo-root>/data/artifacts/backups/phase3c/<backup_stamp> \
  --replace-collection
```

Safety behavior:

- SQLite target is preserved before restore as `recall.db.pre_restore_<timestamp>.bak`.
- `--replace-collection` is destructive for the Qdrant collection and should be used for full recovery testing only.

## Recovery smoke test

1. Create a backup.
2. Run restore with `--replace-collection`.
3. Run preflight.
4. Re-run core eval suite and confirm pass.

```bash
<server-repo-root>/scripts/phase3/run_backup_now.sh
<server-repo-root>/scripts/phase3/run_restore_now.sh --replace-collection
<server-repo-root>/scripts/phase3/run_service_preflight_now.sh
python3 <server-repo-root>/scripts/eval/run_eval.py \
  --cases-file <server-repo-root>/scripts/eval/eval_cases.json \
  --backend webhook \
  --webhook-url http://localhost:5678/webhook/recall-query
```

## Portfolio bundle build

Generate an interview-ready evidence bundle from current artifacts:

```bash
<server-repo-root>/scripts/phase3/build_portfolio_bundle_now.sh
```

Output root:

- `<server-repo-root>/data/artifacts/portfolio/phase3c/`
