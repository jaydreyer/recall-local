# Workflow 3: Evaluate + Notify (Phase 6C)

Goal: evaluate newly discovered jobs through the canonical bridge endpoint and send Telegram alerts only for high-fit opportunities in preferred locations (`remote` first, then `twin_cities`).

## Node 1: Webhook Trigger

- Node type: `Webhook`
- HTTP Method: `POST`
- Path: `recall-job-evaluate`
- Response mode: `Last node`

Expected payload:

```json
{
  "job_ids": ["job_abc", "job_xyz"],
  "wait": true
}
```

## Node 2: Normalize Input

- Node type: `Code`
- Code:

```javascript
const body = $json.body || $json;
const ids = Array.isArray(body.job_ids) ? body.job_ids.filter(Boolean) : [];
return [{
  json: {
    job_ids: ids,
    received_count: ids.length,
    wait: body.wait === undefined ? true : !!body.wait
  }
}];
```

## Node 3: Load LLM Settings

- Node type: `HTTP Request`
- Method: `GET`
- URL: `http://localhost:8090/v1/llm-settings`
- Response format: `JSON`

Use expression in a follow-up `Code` node to merge settings into the request envelope:

```javascript
const incoming = $items('Normalize Input', 0, 0).json;
return [{
  json: {
    job_ids: incoming.job_ids,
    wait: incoming.wait,
    settings: $json.settings || {}
  }
}];
```

## Node 4: Evaluate Jobs

- Node type: `HTTP Request`
- Method: `POST`
- URL: `http://localhost:8090/v1/job-evaluation-runs`
- Send body as JSON

Body:

```json
{
  "job_ids": "={{ $json.job_ids }}",
  "wait": "={{ $json.wait }}",
  "settings": "={{ $json.settings }}"
}
```

Notes:

- For this workflow, keep `wait=true` so fit scores are returned immediately.
- Endpoint returns `200` for sync runs and `202` for async runs.

## Node 5: Evaluate + Notify

- Node type: `Code`
- Purpose: keep only alertable jobs that pass both score and preferred-location filters.
- Preferred location buckets come from `evaluation.observation.location.preference_bucket`.
- Alertable buckets:
  - `remote`
  - `twin_cities`
- Score gate:
  - `fit_score >= 75`
  - or `fit_score >= 60 && company_tier in [1,2]`

This node also:
- builds the Telegram message
- counts jobs skipped for non-preferred locations
- caps each Telegram message preview to 5 jobs

## Node 6: If Has High Fit

- Node type: `IF`
- Condition: `high_fit_count > 0`

## Node 7: Telegram Notify

- Node type: `Telegram`
- Resource: `message`
- Operation: `sendMessage`
- Chat ID: `8724583836`
- Text:

```text
={{ $json.telegram_message }}
```

- Credential:
  - type: `telegramApi`
  - name: `Telegram account`
  - id: `6aWx4DnLbVi8JlGU`

- Sends one batched message for the qualifying jobs in the current webhook run.
- Message includes:
  - fit score
  - preference bucket
  - raw location text
  - job URL

## Node 8: Run Summary

- Node type: `Code`
- Captures:
  - `result_count`
  - `high_fit_count`
  - `skipped_location_count`
  - `notifications_sent`
  - `notification_errors`

## Respond to Webhook

- Node type: `Respond to Webhook`
- Status code: `200`
- Body: `={{ $json }}`

## Quick test

```bash
curl -sS -X POST http://localhost:5678/webhook/recall-job-evaluate \
  -H 'content-type: application/json' \
  -d '{"job_ids":["job_1","job_2"],"wait":true}'
```

Expected response includes:

- `run_id`
- `status` (`completed`)
- `evaluated`
- `high_fit_count`
- `skipped_location_count`
- `notifications_sent`
