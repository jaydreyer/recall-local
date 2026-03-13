# Workflow 1: Job Board Aggregator (Guided)

Goal: every 8 hours, run aggregator discovery through bridge, then hand newly discovered jobs to Workflow 3 so evaluation and Telegram notify stay in one path.

## Node 1: Schedule Trigger

- Node type: `Schedule Trigger`
- Mode: `Cron`
- Cron expression: `0 6,14,22 * * *`

## Node 2: Build Discovery Payload

- Node type: `Code`
- Name: `Build Discovery Payload`
- Code:

```javascript
// Keep this explicit so you can tune source usage in one place.
return [
  {
    json: {
      titles: [
        "Solutions Engineer",
        "Solutions Architect",
        "Sales Engineer",
        "Technical Account Manager"
      ],
      locations: ["Remote", "Minneapolis, MN", "Twin Cities, MN"],
      keywords: ["AI", "SaaS", "API"],
      sources: ["jobspy", "adzuna", "serpapi"],
      max_queries: 4,
      max_days_old: 7,
      delay_seconds: 2,
      source_limits: {
        jobspy: 2,
        adzuna: 2,
        serpapi: 1
      },
      dry_run: false
    }
  }
];
```

## Node 3: Trigger Discovery Run

- Node type: `HTTP Request`
- Method: `POST`
- URL: `http://localhost:8090/v1/job-discovery-runs`
- Send body: `JSON`
- JSON body expression: `={{ $json }}`
- Response format: `JSON`

Expected response fields:
- `run_id`
- `new_job_ids[]`
- `duplicates_skipped`
- `source_metrics`
- `errors[]`

## Node 4: If New Jobs

- Node type: `IF`
- Condition (Number):
- Value 1 (expression): `={{ ($json.new_job_ids || []).length }}`
- Operation: `larger`
- Value 2: `0`

## Node 5: Trigger Evaluation Workflow

- Node type: `HTTP Request`
- Method: `POST`
- URL: `http://localhost:5678/webhook/recall-job-evaluate`
- Send body: `JSON`
- JSON body:

```javascript
={{ {
  job_ids: $json.new_job_ids,
  wait: true
} }}
```

- This keeps all notify gating and Telegram delivery inside Workflow 3 instead of bypassing it through the bridge evaluation endpoint.

## Node 6: Log Summary

- Node type: `Code`
- Name: `Log Summary`
- Code:

```javascript
const newCount = ($json.new_job_ids || []).length;
const dupes = $json.duplicates_skipped || 0;
const sources = ($json.sources || []).join(", ");
return [{
  json: {
    message: `Discovered ${newCount} new jobs, skipped ${dupes} duplicates from ${sources}`,
    run_id: $json.run_id,
    source_metrics: $json.source_metrics,
    errors: $json.errors || []
  }
}];
```

## Quick test

1. Click `Execute workflow`.
2. Confirm Node 3 returns `new_job_ids` (can be empty if no new jobs).
3. If Node 4 true path runs, confirm Node 5 returns Workflow 3 summary fields such as `run_id`, `high_fit_count`, and `notifications_sent`.
4. Check bridge jobs endpoint:

```bash
curl -sS "http://localhost:8090/v1/jobs?status=new&limit=10"
```
