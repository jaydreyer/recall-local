# Recall.local Eval Scheduling

Purpose: run automated Workflow 02 eval checks on a schedule and alert on regression.

## Files

- Runner: `/Users/jaydreyer/projects/recall-local/scripts/eval/scheduled_eval.sh`
- Alert helper: `/Users/jaydreyer/projects/recall-local/scripts/eval/notify_regression.py`
- Core harness: `/Users/jaydreyer/projects/recall-local/scripts/eval/run_eval.py`

## Environment variables

- `RECALL_EVAL_WEBHOOK_URL` (optional)
  - default: `http://100.116.103.78:5678/webhook/recall-query`
- `RECALL_ALERT_WEBHOOK_URL` (optional)
  - Slack/Teams-compatible incoming webhook URL.
  - If unset, regressions still fail the job and write logs, but no webhook is sent.
- `RECALL_EVAL_LOG_DIR` (optional)
  - default: `/home/jaydreyer/recall-local/data/artifacts/evals/scheduled`

## Manual run

```bash
/home/jaydreyer/recall-local/scripts/eval/scheduled_eval.sh
```

## Cron setup (ai-lab)

Open crontab:

```bash
crontab -e
```

Add daily and weekly checks:

```cron
# Daily at 09:00 UTC
0 9 * * * RECALL_EVAL_WEBHOOK_URL="http://100.116.103.78:5678/webhook/recall-query" RECALL_ALERT_WEBHOOK_URL="https://hooks.slack.com/services/REPLACE_ME" /home/jaydreyer/recall-local/scripts/eval/scheduled_eval.sh >> /home/jaydreyer/recall-local/data/artifacts/evals/scheduled/cron.log 2>&1

# Weekly Sunday at 09:15 UTC
15 9 * * 0 RECALL_EVAL_WEBHOOK_URL="http://100.116.103.78:5678/webhook/recall-query" RECALL_ALERT_WEBHOOK_URL="https://hooks.slack.com/services/REPLACE_ME" /home/jaydreyer/recall-local/scripts/eval/scheduled_eval.sh >> /home/jaydreyer/recall-local/data/artifacts/evals/scheduled/cron.log 2>&1
```

## Behavior

- Pass case:
  - exits `0`
  - writes eval JSON artifact to scheduled log dir.
- Regression/failure:
  - exits non-zero
  - prints summary with run_id + pass stats
  - posts alert webhook if `RECALL_ALERT_WEBHOOK_URL` is set.
