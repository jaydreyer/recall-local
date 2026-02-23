# Phase 2A Workflow 03 Wiring (Meeting -> Action Items)

Purpose: wire n8n Workflow 03 so `/webhook/recall-meeting-actions` extracts action items from transcript payloads.

## Import-ready workflow files

- Execute Command path:
  - `/home/jaydreyer/recall-local/n8n/workflows/phase2a_meeting_action_items.workflow.json`
- HTTP bridge path (use if `Execute Command` node is unavailable):
  - `/home/jaydreyer/recall-local/n8n/workflows/phase2a_meeting_action_items_http.workflow.json`

## Endpoint contract

`POST /webhook/recall-meeting-actions`

Example payload:

```json
{
  "meeting_title": "Weekly Product Sync",
  "transcript": "Alice: ship onboarding fix Friday. Bob: QA sign-off due Thursday.",
  "source": "webhook",
  "source_ref": "meeting://weekly-product-sync/2026-02-23",
  "tags": ["meeting", "product"]
}
```

Sample payload file:

- `/home/jaydreyer/recall-local/n8n/workflows/payload_examples/meeting_action_items_payload_example.json`

## Option A: Execute Command workflow

1. In n8n UI, import `phase2a_meeting_action_items.workflow.json`.
2. Open node `Execute Meeting Action Items` and confirm command:

```bash
python3 /home/jaydreyer/recall-local/scripts/phase2/meeting_from_payload.py --payload-base64 "={{ Buffer.from(JSON.stringify($json)).toString('base64') }}"
```

3. Activate workflow.

## Option B: HTTP bridge workflow

Use this when `Execute Command` is not available in your n8n deployment.

1. Ensure bridge service is running:

```bash
cd /home/jaydreyer/recall-local
docker compose -f docker/phase1b-ingest-bridge.compose.yml up -d
```

2. Verify bridge health:

```bash
curl -sS http://localhost:8090/healthz
```

3. Import `phase2a_meeting_action_items_http.workflow.json` into n8n.
4. Confirm node `Webhook Recall Meeting Actions` uses `Response Mode = Last Node`.
5. Confirm node `HTTP Meeting Action Items` URL is:

```text
http://100.116.103.78:8090/meeting/action-items
```

If n8n and bridge are on the same Docker network, `http://recall-ingest-bridge:8090/meeting/action-items` also works.
6. Confirm node `HTTP Meeting Action Items` JSON body expression is:

```text
={{ $json.body }}
```

7. Activate workflow.

## Live validation

Run from `ai-lab` after activation:

```bash
curl -sS -X POST http://localhost:5678/webhook/recall-meeting-actions \
  -H 'content-type: application/json' \
  -d @/home/jaydreyer/recall-local/n8n/workflows/payload_examples/meeting_action_items_payload_example.json
```

Expected response shape:

- `workflow=workflow_03_meeting_action_items`
- nested result includes:
  - `meeting_title`
  - `summary`
  - `action_items[]` with `owner`, `due_date`, `description`
  - `audit` metadata

## Notes

- Workflow 03 code path:
  - `/home/jaydreyer/recall-local/scripts/phase2/meeting_action_items.py`
  - `/home/jaydreyer/recall-local/scripts/phase2/meeting_from_payload.py`
  - `/home/jaydreyer/recall-local/scripts/validate_output.py`
- Artifact outputs (non-dry-run):
  - `/home/jaydreyer/recall-local/data/artifacts/meetings/`
