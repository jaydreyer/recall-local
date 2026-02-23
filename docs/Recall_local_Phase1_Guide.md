# Recall.local - Phase 1 Kickoff Guide

Purpose: track Phase 1 execution for Workflow 01 ingestion, channel wiring, and Workflow 02 cited RAG.

## What Phase 1 currently includes

- `scripts/phase1/ingestion_pipeline.py`
  - Shared ingestion engine for `file`, `url`, `text`, `email`, and `gdoc` payload types.
  - Extracts text, performs heading-aware chunking, embeds via `scripts/llm_client.py`, upserts to Qdrant, logs to SQLite.
  - Moves ingested files from `DATA_INCOMING` to `DATA_PROCESSED`.
- `scripts/phase1/ingest_from_payload.py`
  - Ingests unified webhook payloads from file, stdin, or inline JSON.
  - Supports email body ingestion and optional attachment fan-out.
- `scripts/phase1/ingest_incoming_once.py`
  - One-pass folder ingestion runner for files currently in `DATA_INCOMING`.
- `scripts/phase1/rag_query.py`
  - Workflow 02 cited RAG runner with retrieval, strict output validation, and retry.

## Prerequisites

- Phase 0 complete and services reachable:
  - Ollama at `OLLAMA_HOST`
  - Qdrant at `QDRANT_HOST`
  - SQLite DB at `RECALL_DB_PATH`
- Environment configured in:
  - `/Users/jaydreyer/projects/recall-local/docker/.env`
  - `/Users/jaydreyer/projects/recall-local/docker/.env.example`

## Quick smoke commands

Dry run (no Qdrant or SQLite writes):

```bash
python3 /Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py \
  --type text \
  --content "Recall.local Phase 1 smoke content." \
  --source manual \
  --dry-run
```

Ingest webhook payload JSON:

```bash
python3 /Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_from_payload.py \
  --payload-json '{"type":"url","content":"https://example.com","source":"manual","metadata":{"tags":["phase1"]}}'
```

Ingest files in incoming folder:

```bash
python3 /Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_incoming_once.py
```

Run cited RAG query (Workflow 02):

```bash
python3 /Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py \
  --query "What channels are indexed in recall_docs?" \
  --top-k 5 \
  --min-score 0.2
```

Run cited RAG from webhook-style payload:

```bash
python3 /Users/jaydreyer/projects/recall-local/scripts/phase1/rag_from_payload.py \
  --payload-json '{"query":"Summarize ingestion channels and cite sources.","top_k":5,"min_score":0.2}'
```

## Phase 1 sub-phases

Phase 1 is now tracked as four sub-phases with hard gates:

| Sub-phase | Scope | Status | Exit criteria |
|---|---|---|---|
| `1A` Ingestion Core | Shared ingestion engine and CLI entrypoints for folder + webhook payloads. | Completed | Scripts ingest `file`, `url`, `text`, and `email` payloads through one code path and produce run metadata. |
| `1B` Channel Wiring | Wire n8n webhook flow to ingestion backend; enable Gmail forward-to-ingest and iOS share payload shape. | Completed | Real PDF drop, shared URL, and forwarded email attachment are all searchable in `recall_docs`. |
| `1C` Cited RAG | Implement Workflow 02 request path with retrieval, strict citation schema, citation existence validation, and retry. | Completed | Three demo queries return valid citations (`doc_id` + `chunk_id`) with no fabricated references. |
| `1D` Eval Gate | Build `scripts/eval/` harness (10+ checks), SQLite eval persistence, and Markdown artifact output. | Completed | Eval suite passes green with citation-validity and latency thresholds enforced. |

## Execution order

1. Close `1B` first so all ingestion channels feed one stable backend.
2. Build `1C` against indexed data from `1B`.
3. Finish `1D` as the release gate for Phase 1 completion.

## 1B kickoff deliverables

- Channel adapter + runner scripts:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/channel_adapters.py`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_channel_payload.py`
- n8n runbook:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/PHASE1B_CHANNEL_WIRING.md`
- n8n import-ready workflow exports:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase1b_recall_ingest_webhook.workflow.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase1b_gmail_forward_ingest.workflow.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase1b_recall_ingest_webhook_http.workflow.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase1b_gmail_forward_ingest_http.workflow.json`
- HTTP bridge fallback for n8n environments without `Execute Command`:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_bridge_api.py`
  - `/Users/jaydreyer/projects/recall-local/docker/phase1b-ingest-bridge.compose.yml`
- Example channel payloads:
  - `/Users/jaydreyer/projects/recall-local/shortcuts/ios_send_to_recall_payload_example.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/gmail_forward_payload_example.json`

## 1B live verification status (2026-02-22)

- Backend ingestion checks completed against runtime endpoints:
  - Ollama: `http://100.116.103.78:11434`
  - Qdrant: `http://100.116.103.78:6333`
- Verified successful ingestion for:
  - folder/PDF channel (`folder-watcher`)
  - iOS URL-share channel (`ios-shortcut`)
  - Gmail body + attachment channel (`gmail-forward`)
- Observed Qdrant growth:
  - `recall_docs` points `0 -> 5`
- 1B completion note:
  - this guide originally tracked an n8n editor import gap; `IMPLEMENTATION_LOG.md` now marks 1B exit criteria complete based on live ingestion verification.

## 1C kickoff deliverables

- Workflow 02 retrieval:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/retrieval.py`
- Workflow 02 query runners:
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`
  - `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_from_payload.py`
- n8n workflow exports + runbook:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase1c_recall_rag_query.workflow.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/phase1c_recall_rag_query_http.workflow.json`
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/PHASE1C_WORKFLOW02_WIRING.md`
- Output validator:
  - `/Users/jaydreyer/projects/recall-local/scripts/validate_output.py`
- Prompt templates:
  - `/Users/jaydreyer/projects/recall-local/prompts/workflow_02_rag_answer.md`
  - `/Users/jaydreyer/projects/recall-local/prompts/workflow_02_rag_answer_retry.md`
- Payload example:
  - `/Users/jaydreyer/projects/recall-local/n8n/workflows/payload_examples/rag_query_payload_example.json`

## 1C verification status (2026-02-22)

- Live queries executed against:
  - Ollama: `http://100.116.103.78:11434`
  - Qdrant: `http://100.116.103.78:6333`
- Three demo queries completed with valid citations (`doc_id` + `chunk_id`) and no fabricated citation pairs:
  - run_id `e9310c04d1194383b39c7e5a68f5cbc8` (dry run)
  - run_id `1ced94ff0d8e4e9db6630a07fe6f70d4` (dry run)
  - run_id `a889edf87498486ab9b5923fb8acc107` (dry run)
- Non-dry-run workflow execution also verified:
  - run_id `610b129b66754422996c3cb177a84973`
  - artifact: `/Users/jaydreyer/projects/recall-local/data/artifacts/rag/20260222T223255Z_610b129b66754422996c3cb177a84973.json`

## 1C deployment lessons (carry forward)

- Debug workflow failures from n8n `Executions` first; do not guess from webhook status code alone.
- If failed node is `Execute Command` with `/bin/sh: python3: not found`, switch to HTTP bridge workflow path for Workflow 02.
- For webhook input, send only request body to RAG runner in HTTP node:
  - `={{ $json.body }}`
- In mixed-network setups, use ai-lab host URL in HTTP node:
  - `http://100.116.103.78:8090/query/rag`
- Keep bridge route validation as first check before n8n webhook retest:
  - `curl -sS -X POST 'http://localhost:8090/query/rag?dry_run=true' -H 'content-type: application/json' -d '{"query":"smoke test","top_k":5,"min_score":0.15}'`
- Ensure Workflow 02 scripts are synced to `/home/jaydreyer/recall-local/scripts/phase1/` on ai-lab before troubleshooting n8n wiring.

## 1D kickoff deliverables

- Eval runner:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/run_eval.py`
- Default eval cases:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/eval_cases.json`
- Eval runbook:
  - `/Users/jaydreyer/projects/recall-local/docs/Recall_local_Phase1D_Eval_Guide.md`

## 1D verification status (2026-02-23)

- Eval harness run completed against live Workflow 02 webhook:
  - backend: `webhook`
  - webhook URL: `http://100.116.103.78:5678/webhook/recall-query`
- Current canonical run (expanded bank):
  - run_id `0ee745eada024070815f249d85d3337e`
  - pass rate `15/15`
  - unanswerable pass rate `5/5`
  - artifact: `/home/jaydreyer/recall-local/data/artifacts/evals/20260223T000357Z_0ee745eada024070815f249d85d3337e.md`
- Historical context:
  - baseline pass run `10/10`: `310287389df24e58aa1899a859ad2dcf`
  - first expanded run before hardening `10/15` (`0/5` unanswerable): `acc53692280540cfb02d1476d89119ef`
- Hardening shipped and validated:
  - `scripts/phase1/rag_query.py` now normalizes low-confidence non-abstaining answers to explicit abstention and converts validation failures into structured fallback responses.
  - `scripts/eval/run_eval.py` grades unanswerable cases with abstention-first criteria.

## Phase 1 completion gate

Phase 1 is complete only when all of the following are true:

1. PDF drop, URL share, and email attachment ingestion all index successfully in Qdrant.
2. RAG answers for demo questions include valid citations to existing chunks.
3. Eval harness (10+ questions) runs green and writes artifact output.
