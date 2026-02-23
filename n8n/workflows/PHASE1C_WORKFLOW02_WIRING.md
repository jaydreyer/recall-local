# Phase 1C Workflow 02 Wiring (Cited RAG)

Purpose: wire n8n Workflow 02 so `/webhook/recall-query` runs cited RAG and returns validated JSON.

## Import-ready workflow files

- Execute Command path:
  - `/home/jaydreyer/recall-local/n8n/workflows/phase1c_recall_rag_query.workflow.json`
- HTTP bridge path (use if `Execute Command` node is unavailable):
  - `/home/jaydreyer/recall-local/n8n/workflows/phase1c_recall_rag_query_http.workflow.json`

## Endpoint contract

`POST /webhook/recall-query`

Example payload:

```json
{
  "query": "Identify one URL-based item and one email-related item with citations.",
  "top_k": 5,
  "min_score": 0.15,
  "max_retries": 1
}
```

## Option A: Execute Command workflow

1. In n8n UI, import `phase1c_recall_rag_query.workflow.json`.
2. Open node `Execute RAG Query` and confirm command:

```bash
python3 /home/jaydreyer/recall-local/scripts/phase1/rag_from_payload.py --payload-base64 "={{ Buffer.from(JSON.stringify($json)).toString('base64') }}"
```

3. Activate workflow.

## Option B: HTTP bridge workflow

Use this when `Execute Command` is not available in your n8n deployment.

1. Ensure bridge service is running on `ai-lab`:

```bash
cd /home/jaydreyer/recall-local
docker compose -f docker/phase1b-ingest-bridge.compose.yml up -d
```

2. Verify bridge health:

```bash
curl -sS http://localhost:8090/healthz
```

3. Import `phase1c_recall_rag_query_http.workflow.json` into n8n.
4. Confirm node `Webhook Recall Query` uses `Response Mode = Last Node`.
5. Confirm node `HTTP RAG Query` URL is:

```text
http://100.116.103.78:8090/query/rag
```

If your n8n and bridge containers are on the same Docker network, `http://recall-ingest-bridge:8090/query/rag` also works.
6. Confirm `HTTP RAG Query` JSON body expression is:

```text
={{ $json.body }}
```

6. Activate workflow.

## Live validation

Run from `ai-lab` after activation:

```bash
curl -sS -X POST http://localhost:5678/webhook/recall-query \
  -H 'content-type: application/json' \
  -d '{"query":"What ingestion channels are represented?","top_k":5,"min_score":0.15}'
```

Expected response shape:

- `received=true`
- `workflow=workflow_02_rag_query`
- nested RAG output includes:
  - `answer`
  - `citations[]` with `doc_id` + `chunk_id`
  - `audit` metadata

## Notes

- Workflow 02 code path:
  - `/home/jaydreyer/recall-local/scripts/phase1/rag_query.py`
  - `/home/jaydreyer/recall-local/scripts/phase1/rag_from_payload.py`
  - `/home/jaydreyer/recall-local/scripts/validate_output.py`
- Artifact outputs (non-dry-run):
  - `/home/jaydreyer/recall-local/data/artifacts/rag/`
