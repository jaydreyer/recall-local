# Recall.local Release Checklist

Purpose: provide a reproducible pre-release, tag, and rollback flow for Phase 4 operations.

## Tag Convention (`v0.x-*`)

Use monotonic `v0` tags with explicit release intent:

- Release candidate: `v0.<minor>.<patch>-rc.<n>`
- Stable release: `v0.<minor>.<patch>-r<YYYYMMDD>`

Examples:

- `v0.4.0-rc.1`
- `v0.4.0-r20260224`

Before creating a tag, verify current progression:

```bash
git fetch --tags
git tag --list 'v0.*' --sort=-version:refname | head -n 10
```

## Pre-Release Gate (required)

1. Confirm local repo is clean and on expected base:

```bash
git status --short --branch
git pull --ff-only origin main
```

2. Run local quality checks (same class as CI gate):

```bash
bash -n scripts/phase4/run_eval_soak_now.sh
bash -n scripts/phase4/run_repo_hygiene_check.sh
python3 -m py_compile scripts/phase4/summarize_eval_trend.py
python3 -m py_compile scripts/eval/run_eval.py
```

3. Run soak trend gate (`4A`) and verify summary status.
   Current ai-lab calibrated profile:
   - `min_pass_rate=0.95`
   - `max_avg_latency_ms=45000`

```bash
scripts/phase4/run_eval_soak_now.sh \
  --iterations 5 \
  --suite both \
  --delay-seconds 5 \
  --min-pass-rate 0.95 \
  --max-avg-latency-ms 45000
```

4. Run hygiene gate (`4C`) and resolve any findings:

```bash
scripts/phase4/run_repo_hygiene_check.sh
```

5. Ensure PR checks are green (GitHub Actions `quality-checks` workflow).

6. Run the manual chat QA pass in:

- `<repo-root>/docs/Recall_local_RAG_UI_QA_Checklist.md`

7. If the release changes RAG retrieval, prompts, validation, or model selection, run the model bakeoff and save the artifact path:

```bash
scripts/eval/run_rag_model_bakeoff.sh
```

## ai-lab Sync Gate (required before runtime validation)

Always sync local updates before any ai-lab restart/curl/n8n validation:

```bash
rsync -avz --delete \
  -e "ssh -i ~/.ssh/codex_ai_lab" \
  --exclude '.git/' \
  <repo-root>/ \
  jaydreyer@<ai-lab-tailnet-ip>:<server-repo-root>/
```

Then spot-check remote content before runtime troubleshooting:

```bash
ssh -i ~/.ssh/codex_ai_lab jaydreyer@<ai-lab-tailnet-ip> \
  "cd <server-repo-root> && rg -n 'run_eval_soak_now|run_repo_hygiene_check|quality-checks' scripts .github/workflows"
```

If full `--delete` sync encounters permission errors under runtime-owned artifact folders, run targeted sync for changed code/docs paths and re-run the same `rg` spot-check.

## Release Tag + Push Sequence

1. Prepare changelog note text (summary + evidence artifact paths).
2. Create an annotated tag on the release commit:

```bash
git tag -a v0.4.0-r20260224 -m "Recall.local v0.4.0 release: Phase 4 milestone update"
```

3. Push branch and tag:

```bash
git push origin main
git push origin v0.4.0-r20260224
```

4. Verify on GitHub that tag points to intended commit and CI status is green.

## Rollback Steps

If release validation fails after deployment:

1. Identify previous stable tag:

```bash
git tag --list 'v0.*-r*' --sort=-version:refname | head -n 2
```

2. Check out previous stable tag in local repo:

```bash
git checkout <previous_stable_tag>
```

3. Sync rollback code state to ai-lab and spot-check files.
4. Perform deterministic restart and service preflight on ai-lab:

```bash
scripts/phase3/run_deterministic_restart_now.sh --wait-timeout-seconds 180
scripts/phase3/run_service_preflight_now.sh
```

5. If data integrity is impacted, run restore workflow with latest known-good backup:

```bash
scripts/phase3/run_restore_now.sh --backup-dir <server-repo-root>/data/artifacts/backups/phase3c/<backup_name> --replace-collection
```

6. Re-run core eval gate and archive evidence artifact path in release notes.
