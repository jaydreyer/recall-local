# Workflow 3: Evaluate + Notify (Phase 6C)

Goal: evaluate newly discovered jobs through the canonical bridge endpoint and send Telegram alerts for high-fit opportunities.

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

## Node 5: Flatten Evaluation Results

- Node type: `Code`
- Code:

```javascript
const results = Array.isArray($json.results) ? $json.results : [];
return results.map((row) => ({
  json: {
    run_id: $json.run_id,
    job_id: row.job_id,
    status: row.status,
    fit_score: row.fit_score,
    evaluation: row.evaluation || {}
  }
}));
```

## Node 6: Wait Between Alerts

- Node type: `Wait`
- Wait amount: `2` seconds

## Node 7: Score Gate

- Node type: `IF`
- Condition (Expression):

```javascript
{{
  const score = Number($json.fit_score || -1);
  const tier = Number($json.evaluation?.company_tier || 0);
  return score >= 75 || (score >= 60 && [1,2].includes(tier));
}}
```

`true` path => Telegram notification.

`false` path => no alert.

## Node 8: Telegram Notify (true path)

- Node type: `HTTP Request`
- Method: `POST`
- URL:

```text
=https://api.telegram.org/bot{{$env.RECALL_TELEGRAM_BOT_TOKEN}}/sendMessage
```

Body JSON:

```json
{
  "chat_id": "={{ $env.RECALL_TELEGRAM_CHAT_ID }}",
  "text": "={{ `Job fit alert\nJob: ${$json.evaluation?.title || $json.job_id}\nCompany: ${$json.evaluation?.company || 'Unknown'}\nScore: ${$json.fit_score}\nURL: ${$json.evaluation?.url || 'n/a'}` }}"
}
```

## Node 9: Run Summary

- Node type: `Code`
- Run this after merge/aggregation of both IF branches.
- Example summary output:

```javascript
const items = $input.all().map(i => i.json);
const scores = items.map(i => Number(i.fit_score || -1)).filter(s => s >= 0);
const sent = items.filter(i => i.telegram_sent === true).length;
return [{
  json: {
    summary: `Evaluated ${items.length} jobs. Scores: ${scores.length ? Math.min(...scores) : 'n/a'}-${scores.length ? Math.max(...scores) : 'n/a'}. ${sent} notifications sent.`
  }
}];
```

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
- `results[]` with `fit_score`
