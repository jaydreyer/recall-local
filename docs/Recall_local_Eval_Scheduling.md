# Recall.local Eval Scheduling

Purpose: run automated Workflow 02 eval checks on a schedule and alert on regression.

## Files

- Runner: `<repo-root>/scripts/eval/scheduled_eval.sh`
- Alert helper: `<repo-root>/scripts/eval/notify_regression.py`
- Core harness: `<repo-root>/scripts/eval/run_eval.py`

## Environment variables

- `RECALL_EVAL_WEBHOOK_URL` (optional)
  - default: `${N8N_HOST:-http://localhost:5678}/webhook/recall-query`
- `RECALL_EVAL_CORE_CASES_FILE` (optional)
  - default: `<server-repo-root>/scripts/eval/eval_cases.json`
- `RECALL_EVAL_JOB_SEARCH_CASES_FILE` (optional)
  - default: `<server-repo-root>/scripts/eval/job_search_eval_cases.json`
- `RECALL_EVAL_LEARNING_CASES_FILE` (optional)
  - default: `<server-repo-root>/scripts/eval/learning_eval_cases.json`
- `RECALL_EVAL_INCLUDE_LEARNING` (optional)
  - default: `false`
  - when `true`, scheduled runs include learning suite in addition to core + job-search.
- `RECALL_EVAL_RETRY_ON_FAIL` (optional)
  - default: `true`
  - when `true`, each suite is retried once before alert/fail handling.
- `RECALL_EVAL_RETRY_DELAY_SECONDS` (optional)
  - default: `5`
  - sleep duration between first attempt and retry.
- `RECALL_ALERT_WEBHOOK_URL` (optional)
  - Slack/Teams-compatible incoming webhook URL.
  - If unset, regressions still fail the job and write logs, but no webhook is sent.
- `RECALL_EVAL_LOG_DIR` (optional)
  - default: `<server-repo-root>/data/artifacts/evals/scheduled`

## Manual run

```bash
<server-repo-root>/scripts/eval/scheduled_eval.sh
```

## Cron setup (ai-lab)

Open crontab:

```bash
crontab -e
```

Add daily and weekly checks:

```cron
# Daily at 09:00 UTC (core + job-search only)
0 9 * * * N8N_HOST="http://localhost:5678" RECALL_ALERT_WEBHOOK_URL="https://hooks.slack.com/services/REPLACE_ME" <server-repo-root>/scripts/eval/scheduled_eval.sh >> <server-repo-root>/data/artifacts/evals/scheduled/cron.log 2>&1

# Weekly Sunday at 09:15 UTC (include learning suite)
15 9 * * 0 N8N_HOST="http://localhost:5678" RECALL_EVAL_INCLUDE_LEARNING="true" RECALL_ALERT_WEBHOOK_URL="https://hooks.slack.com/services/REPLACE_ME" <server-repo-root>/scripts/eval/scheduled_eval.sh >> <server-repo-root>/data/artifacts/evals/scheduled/cron.log 2>&1
```

## Behavior

- Pass case:
  - exits `0`
  - writes core + job-search eval JSON artifacts to scheduled log dir.
  - if `RECALL_EVAL_INCLUDE_LEARNING=true`, also writes learning eval JSON artifact.
- Regression/failure:
  - exits non-zero
  - prints summary with run_id + pass stats for all suites
  - posts alert webhook if `RECALL_ALERT_WEBHOOK_URL` is set.
