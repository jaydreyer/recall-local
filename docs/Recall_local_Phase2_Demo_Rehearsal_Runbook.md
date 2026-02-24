# Recall.local Phase 2 Demo Rehearsal Runbook

Purpose: run and record one full Phase 2 rehearsal with a single timestamped log file.

## What this verifies

1. Bridge health and basic service readiness.
2. Multi-channel ingestion in one rehearsal window.
3. Workflow 02 responses for:
   - default mode
   - job-search mode
   - learning mode
4. Eval gates:
   - core suite
   - job-search suite
   - learning suite

## Recommended method (one command)

Use the helper script:

```bash
/home/jaydreyer/recall-local/scripts/rehearsal/run_phase2_demo_rehearsal.sh
```

The script writes a timestamped log under:

- `/home/jaydreyer/recall-local/data/artifacts/rehearsals/`

It prints `LOG_FILE=...` at the end so you can copy the exact path into implementation notes.

## Manual method (copy/paste)

```bash
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="/home/jaydreyer/recall-local/data/artifacts/rehearsals/${STAMP}_phase2_demo_rehearsal.log"
N8N_HOST="${N8N_HOST:-http://localhost:5678}"
WEBHOOK_URL="${RECALL_EVAL_WEBHOOK_URL:-${N8N_HOST%/}/webhook/recall-query}"
mkdir -p /home/jaydreyer/recall-local/data/artifacts/rehearsals
exec > >(tee -a "$LOG") 2>&1

echo "=== Phase 2 demo rehearsal start: $STAMP ==="

# 1) Health checks
curl -sS http://localhost:8090/healthz
curl -sS http://localhost:5678/healthz || true

# 2) Ingestion channels (same rehearsal)
python3 - <<'PY' | curl -sS -X POST "http://localhost:8090/v1/ingestions?dry_run=true" -H "content-type: application/json" -d @-
import json
payload = json.load(open("/home/jaydreyer/recall-local/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json", "r", encoding="utf-8"))
payload["channel"] = "bookmarklet"
print(json.dumps(payload))
PY

python3 - <<'PY' | curl -sS -X POST "http://localhost:8090/v1/ingestions?dry_run=true" -H "content-type: application/json" -d @-
import json
payload = json.load(open("/home/jaydreyer/recall-local/n8n/workflows/payload_examples/gdoc_ingest_payload_example.json", "r", encoding="utf-8"))
payload["channel"] = "webhook"
print(json.dumps(payload))
PY

curl -sS -X POST "http://localhost:8090/v1/meeting-action-items?dry_run=true" \
  -H "content-type: application/json" \
  -d @/home/jaydreyer/recall-local/n8n/workflows/payload_examples/meeting_action_items_payload_example.json

# 3) RAG checks (default + job-search + learning)
curl -sS -X POST "http://localhost:8090/v1/rag-queries?dry_run=true" \
  -H "content-type: application/json" \
  -d '{"query":"Summarize indexed content with citations.","mode":"default","top_k":5,"min_score":0.15}'

curl -sS -X POST "http://localhost:8090/v1/rag-queries?dry_run=true" \
  -H "content-type: application/json" \
  -d '{"query":"What should I emphasize for an Anthropic SE interview?","mode":"job-search","filter_tags":["job-search"],"top_k":5,"min_score":0.15}'

curl -sS -X POST "http://localhost:8090/v1/rag-queries?dry_run=true" \
  -H "content-type: application/json" \
  -d '{"query":"Summarize RAG architecture tradeoffs for enterprise use.","mode":"learning","filter_tags":["learning","genai-docs"],"top_k":5,"min_score":0.2,"max_retries":0}'

# 4) Eval gates
python3 /home/jaydreyer/recall-local/scripts/eval/run_eval.py \
  --cases-file /home/jaydreyer/recall-local/scripts/eval/eval_cases.json \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL"

python3 /home/jaydreyer/recall-local/scripts/eval/run_eval.py \
  --cases-file /home/jaydreyer/recall-local/scripts/eval/job_search_eval_cases.json \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL"

python3 /home/jaydreyer/recall-local/scripts/eval/run_eval.py \
  --cases-file /home/jaydreyer/recall-local/scripts/eval/learning_eval_cases.json \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL"

echo "=== Phase 2 demo rehearsal end: $(date -u +%Y%m%dT%H%M%SZ) ==="
echo "LOG_FILE=$LOG"
```

## Pass criteria for "clean end-to-end"

1. No command exits non-zero (except optional n8n health probe line with `|| true`).
2. Core eval returns pass.
3. Job-search eval returns pass.
4. Learning eval returns pass.
5. Log file exists under `/data/artifacts/rehearsals/`.

## After rehearsal

Add one entry to:

- `/Users/jaydreyer/projects/recall-local/docs/IMPLEMENTATION_LOG.md`

Include:

1. rehearsal timestamp
2. `LOG_FILE=...`
3. summary (`core/job-search/learning` pass counts)
