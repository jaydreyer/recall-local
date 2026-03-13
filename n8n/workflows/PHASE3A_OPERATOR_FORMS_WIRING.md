# Phase 3A Operator Form Wiring (n8n)

Purpose: import two operator-focused HTTP workflows so bookmarklet ingestion and meeting action extraction can be triggered from dedicated webhook/form endpoints.

## Import-ready workflow files

- `/home/jaydreyer/recall-local/n8n/workflows/phase3a_bookmarklet_form_http.workflow.json`
- `/home/jaydreyer/recall-local/n8n/workflows/phase3a_meeting_action_form_http.workflow.json`

## Prerequisites

1. Bridge service running on ai-lab:

```bash
cd /home/jaydreyer/recall-local
docker compose -f docker/phase1b-ingest-bridge.compose.yml up -d
curl -sS http://localhost:8090/healthz
```

2. n8n available at `http://localhost:5678` on ai-lab host.

## Workflow A: Bookmarklet Form Ingest

- Webhook path: `POST /webhook/recall-bookmarklet-form`
- Bridge target: `POST http://localhost:8090/v1/ingestions` with `channel=bookmarklet` in JSON body
- Payload contract: same as bookmarklet payload example:
  - `/home/jaydreyer/recall-local/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json`

Smoke test:

```bash
curl -sS -X POST http://localhost:5678/webhook/recall-bookmarklet-form \
  -H 'content-type: application/json' \
  -d @/home/jaydreyer/recall-local/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json
```

## Workflow B: Meeting Action Form

- Webhook path: `POST /webhook/recall-meeting-form`
- Bridge target: `POST http://localhost:8090/v1/meeting-action-items`
- Payload contract: same as meeting payload example:
  - `/home/jaydreyer/recall-local/n8n/workflows/payload_examples/meeting_action_items_payload_example.json`

Smoke test:

```bash
curl -sS -X POST http://localhost:5678/webhook/recall-meeting-form \
  -H 'content-type: application/json' \
  -d @/home/jaydreyer/recall-local/n8n/workflows/payload_examples/meeting_action_items_payload_example.json
```

## Notes

- Both workflows accept either `{{$json.body}}` or `{{$json}}` request shapes.
- Keep these workflows inactive until imported and verified in the target n8n environment.
- These workflow files include explicit `webhookId` values on webhook nodes so production paths stay stable as:
  - `/webhook/recall-bookmarklet-form`
  - `/webhook/recall-meeting-form`
