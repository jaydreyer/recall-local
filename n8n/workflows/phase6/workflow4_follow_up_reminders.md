# Workflow 4: Follow-up Reminders (Application Ops)

Goal: run a scheduled n8n workflow that selects due follow-up reminders through the canonical bridge API, sends the reminder text, then writes delivery status back onto the same job workflow record.

## Node 1: Schedule Trigger

- Node type: `Schedule Trigger`
- Recommended cadence: every weekday morning plus one afternoon catch-up run
- Example:
  - Monday-Friday at `9:00 AM`
  - Monday-Friday at `2:00 PM`

## Node 2: Queue Due Reminders

- Node type: `HTTP Request`
- Method: `POST`
- URL:
  - local host-shell validation: `http://localhost:8090/v1/follow-up-reminder-runs`
  - live ai-lab n8n container import: `http://recall-ingest-bridge:8090/v1/follow-up-reminder-runs`
- Send body as JSON

Body:

```json
{
  "due_only": true,
  "limit": 10,
  "dry_run": false,
  "channel": "n8n",
  "automation_id": "phase6-follow-up-reminder"
}
```

Expected response fields:

- `run_id`
- `queued`
- `skipped`
- `items[]`
- `items[].job_id`
- `items[].message`

## Node 3: If Has Reminders

- Node type: `IF`
- Condition: `={{ Number($json.queued || 0) > 0 }}`

If false:

- End the run or respond with the bridge summary object unchanged.

## Node 4: Split Reminder Items

- Node type: `Code`
- Code:

```javascript
const run = $json || {};
const items = Array.isArray(run.items) ? run.items : [];
return items.map((item) => ({
  json: {
    run_id: run.run_id || null,
    job_id: item.job_id,
    message: item.message,
    channel: item.channel || 'n8n',
    automation_id: item.automation_id || 'phase6-follow-up-reminder',
  }
}));
```

## Node 5: Telegram Send

- Node type: `Telegram`
- Resource: `message`
- Operation: `sendMessage`
- Text:

```text
={{ $json.message }}
```

Current delivery recommendation:

- use the same Telegram credential pattern as the Phase 6C evaluation-notify workflow
- keep bridge selection/business rules in Python and delivery in n8n

## Node 6A: Mark Reminder Sent

- Node type: `HTTP Request`
- Method: `PATCH`
- URL: `={{ 'http://localhost:8090/v1/jobs/' + $json.job_id }}`
- Send body as JSON

Body:

```json
{
  "workflow": {
    "followUp": {
      "reminder": {
        "created": true,
        "status": "sent",
        "channel": "n8n",
        "lastRunAt": "={{ $now.toISO() }}",
        "deliveredAt": "={{ $now.toISO() }}",
        "automationId": "={{ $json.automation_id }}",
        "notes": "Reminder delivered by n8n workflow."
      }
    }
  }
}
```

## Node 6B: Mark Reminder Failed

- Node type: `HTTP Request`
- Method: `PATCH`
- URL: `={{ 'http://localhost:8090/v1/jobs/' + $json.job_id }}`
- Connect this on the Telegram error branch or failure path

Body:

```json
{
  "workflow": {
    "followUp": {
      "reminder": {
        "created": true,
        "status": "failed",
        "channel": "n8n",
        "lastRunAt": "={{ $now.toISO() }}",
        "deliveredAt": null,
        "automationId": "={{ $json.automation_id }}",
        "notes": "Reminder delivery failed in n8n; retry needed."
      }
    }
  }
}
```

## Validation

1. Dry-run from the bridge first:

```bash
curl -sS -X POST http://localhost:8090/v1/follow-up-reminder-runs \
  -H 'content-type: application/json' \
  -d '{"due_only":true,"limit":5,"dry_run":true,"channel":"n8n","automation_id":"phase6-follow-up-reminder"}'
```

2. Confirm at least one due job returns `items[].message`.
3. Run the live workflow once.
4. Verify the affected jobs now show reminder status `sent` or `failed` in Ops.

## Import Artifact

- Import-ready workflow JSON:
  - `n8n/workflows/phase6_follow_up_reminders_import.workflow.json`
- The import artifact includes:
  - `Schedule Trigger` for weekday `9:00 AM` and `2:00 PM`
  - `Manual Trigger` for operator test runs
  - `Webhook Test Trigger` at `/webhook/recall-follow-up-reminders` for targeted validation payloads such as `job_ids` and `force_failure`
