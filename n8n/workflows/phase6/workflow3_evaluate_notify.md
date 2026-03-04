# Workflow 3: Evaluate + Notify Skeleton (Phase 6B)

Goal: provide a callable webhook target so Workflows 1/2 can hand off `job_ids` now. Full AI scoring arrives in Phase 6C.

## Node 1: Webhook Trigger

- Node type: `Webhook`
- HTTP Method: `POST`
- Path: `recall-job-evaluate`
- Response mode: `Last node`

Expected payload:

```json
{
  "job_ids": ["job_abc", "job_xyz"],
  "wait": false
}
```

## Node 2: Normalize Input

- Node type: `Code`
- Code:

```javascript
const body = $json.body || $json;
const ids = Array.isArray(body.job_ids) ? body.job_ids.filter(Boolean) : [];
return [{ json: { job_ids: ids, received_count: ids.length, wait: !!body.wait } }];
```

## Node 3: Placeholder Evaluation Result

- Node type: `Code`
- Code:

```javascript
const ids = $json.job_ids || [];
return [{
  json: {
    run_id: `workflow3_skeleton_${Date.now()}`,
    status: "queued",
    received_count: ids.length,
    job_ids: ids,
    message: `Received ${ids.length} jobs for evaluation (evaluation engine not yet active).`,
    placeholder: {
      fit_score: -1,
      status: "new"
    }
  }
}];
```

## Node 4: Respond

- Node type: `Respond to Webhook`
- Response body: `={{ $json }}`
- Status code: `200`

## Quick test

```bash
curl -sS -X POST http://localhost:5678/webhook/recall-job-evaluate \
  -H 'content-type: application/json' \
  -d '{"job_ids":["job_1","job_2"],"wait":false}'
```

Expected response includes:
- `received_count`
- `job_ids[]`
- `message`
- placeholder status/score
