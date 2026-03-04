# Phase 1B Channel Wiring (n8n)

This runbook wires channel-specific inputs into the shared ingestion backend.

Preferred path: HTTP bridge (works when `Execute Command` is unavailable in n8n).

- Bridge service script: `/home/jaydreyer/recall-local/scripts/phase1/ingest_bridge_api.py`
- Channels supported: `webhook`, `bookmarklet`, `ios-share`, `gmail-forward`
- Import-ready workflow JSON files:
  - `/home/jaydreyer/recall-local/n8n/workflows/phase1b_recall_ingest_webhook.workflow.json`
  - `/home/jaydreyer/recall-local/n8n/workflows/phase1b_gmail_forward_ingest.workflow.json`
  - `/home/jaydreyer/recall-local/n8n/workflows/phase1b_recall_ingest_webhook_http.workflow.json`
  - `/home/jaydreyer/recall-local/n8n/workflows/phase1b_gmail_forward_ingest_http.workflow.json`
  - Use the `_http` files if `Execute Command` appears as an unknown node.

## Start the bridge service (recommended)

From `ai-lab`:

```bash
cd /home/jaydreyer/recall-local
docker compose -f docker/phase1b-ingest-bridge.compose.yml up -d
curl -sS http://localhost:8090/healthz
```

## Workflow A: Unified Webhook (`/webhook/recall-ingest`)

Node sequence:

1. `Webhook` (POST, path `recall-ingest`)
2. `HTTP Request`
3. `Respond to Webhook`

`HTTP Request` settings:

- Method: `POST`
- URL: `={{ ($env.RECALL_BRIDGE_BASE_URL || 'http://100.116.103.78:8090') + '/v1/ingestions' }}`
- Send Body: `true`
- Body Content Type: `JSON`
- JSON Body: `={{ Object.assign({}, ($json.body || $json), { channel: 'webhook' }) }}`

This unified webhook now supports additional payload controls:

- `replace_existing` (boolean): when true, deletes existing chunks for the same source identity before upsert.
- `source_key` (string): stable canonical key used for replacement matching across updates.

`Respond to Webhook` response body example:

```json
{
  "received": true,
  "channel": "webhook",
  "timestamp": "={{ $now.toISO() }}"
}
```

## Workflow B: Gmail Forward-to-Ingest

Node sequence:

1. `Email Trigger (IMAP)` for your Recall inbox
2. Optional `Code` node to map attachment paths to `attachment_paths` if needed
3. `HTTP Request`

`HTTP Request` settings:

- Method: `POST`
- URL: `={{ ($env.RECALL_BRIDGE_BASE_URL || 'http://100.116.103.78:8090') + '/v1/ingestions' }}`
- Send Body: `true`
- Body Content Type: `JSON`
- JSON Body:

```text
={{ ({
  channel: 'gmail-forward',
  subject: $json.subject || '',
  from: (typeof $json.from === 'string' ? $json.from : (($json.from && $json.from.text) ? $json.from.text : '')),
  messageId: $json.messageId || $json.message_id || '',
  text: $json.textPlain || $json.text || ($json.subject ? ('Subject: ' + $json.subject) : ''),
  html: $json.textHtml || $json.html || '',
  attachment_paths: Array.isArray($json.attachment_paths) ? $json.attachment_paths : []
}) }}
```

Expected input shape (minimum):

```json
{
  "subject": "Weekly notes",
  "text": "Email body text",
  "attachment_paths": ["/home/jaydreyer/recall-local/data/incoming/mail/weekly-notes.pdf"]
}
```

## iOS Shortcut payload contract

iOS Shortcut can call the same webhook (`/webhook/recall-ingest`) with either:

```json
{
  "type": "url",
  "content": "https://example.com/article",
  "source": "ios-shortcut",
  "metadata": {
    "title": "Optional Title",
    "tags": ["mobile-share"]
  }
}
```

## Browser bookmarklet payload contract

Bookmarklet should call the same webhook (`/webhook/recall-ingest`) with either a unified payload or raw shape:

```json
{
  "url": "https://example.com/?utm_source=bookmarklet",
  "title": "Solutions Engineer Job Description",
  "text": "Optional selected text from the page",
  "tags": ["job-search", "jd", "exampleco"],
  "replace_existing": true,
  "source_key": "job:exampleco:solutions-engineer",
  "source": "bookmarklet"
}
```

Sample file:
- `/home/jaydreyer/recall-local/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json`

Direct bridge route for bookmarklet testing:

```bash
python3 - <<'PY' | curl -sS -X POST http://localhost:8090/v1/ingestions \
  -H 'content-type: application/json' \
  -d @-
import json
from pathlib import Path
payload = json.loads(Path("/home/jaydreyer/recall-local/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json").read_text())
payload["channel"] = "bookmarklet"
print(json.dumps(payload))
PY
```

## Google Docs payload contract

Google Docs ingestion supports either doc text supplied by n8n or URL/doc id fetch:

```json
{
  "type": "gdoc",
  "content": {
    "doc_id": "1EXAMPLE_DOC_ID",
    "url": "https://docs.google.com/document/d/1EXAMPLE_DOC_ID/edit",
    "title": "Interview Prep Notes",
    "text": "Prepared notes from Google Docs node output"
  },
  "source": "gdocs-sync",
  "replace_existing": true,
  "source_key": "gdoc:interview-prep-notes",
  "metadata": {
    "tags": ["job-search", "prep"]
  }
}
```

Sample file:
- `/home/jaydreyer/recall-local/n8n/workflows/payload_examples/gdoc_ingest_payload_example.json`

Or raw share-shape (adapter-supported):

```json
{
  "sharedUrl": "https://example.com/article",
  "title": "Optional Title",
  "tags": ["mobile-share"]
}
```

## Validation commands (server-side)

Import JSON workflows (from n8n UI):

1. Open n8n editor.
2. `Workflows` -> `Import from file`.
3. Import both workflow JSON files listed above.
4. Prefer the `_http` workflow files when `Execute Command` is unavailable.
5. Configure IMAP credentials on `Recall Phase1B - Gmail Forward Ingest`.

Normalize-only webhook validation:

```bash
python3 /home/jaydreyer/recall-local/scripts/phase1/ingest_channel_payload.py \
  --channel webhook \
  --payload-file /home/jaydreyer/recall-local/shortcuts/ios_send_to_recall_payload_example.json \
  --normalize-only
```

Normalize-only Gmail validation:

```bash
python3 /home/jaydreyer/recall-local/scripts/phase1/ingest_channel_payload.py \
  --channel gmail-forward \
  --payload-file /home/jaydreyer/recall-local/n8n/workflows/payload_examples/gmail_forward_payload_example.json \
  --normalize-only
```
