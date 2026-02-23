#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BRIDGE_URL="${RECALL_BRIDGE_URL:-http://localhost:8090}"
N8N_HOST="${N8N_HOST:-http://localhost:5678}"
N8N_BASE_URL="${N8N_HOST%/}"
WEBHOOK_URL="${RECALL_EVAL_WEBHOOK_URL:-$N8N_BASE_URL/webhook/recall-query}"
N8N_HEALTH_URL="${RECALL_N8N_HEALTH_URL:-$N8N_BASE_URL/healthz}"
ARTIFACT_DIR="${RECALL_REHEARSAL_ARTIFACT_DIR:-$ROOT_DIR/data/artifacts/rehearsals}"

BOOKMARKLET_PAYLOAD="${RECALL_BOOKMARKLET_PAYLOAD_FILE:-$ROOT_DIR/n8n/workflows/payload_examples/bookmarklet_ingest_payload_example.json}"
GDOC_PAYLOAD="${RECALL_GDOC_PAYLOAD_FILE:-$ROOT_DIR/n8n/workflows/payload_examples/gdoc_ingest_payload_example.json}"
MEETING_PAYLOAD="${RECALL_MEETING_PAYLOAD_FILE:-$ROOT_DIR/n8n/workflows/payload_examples/meeting_action_items_payload_example.json}"

mkdir -p "$ARTIFACT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="$ARTIFACT_DIR/${STAMP}_phase2_demo_rehearsal.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Phase 2 demo rehearsal start: $STAMP ==="
echo "ROOT_DIR=$ROOT_DIR"
echo "BRIDGE_URL=$BRIDGE_URL"
echo "WEBHOOK_URL=$WEBHOOK_URL"
echo

echo "[1/4] Health checks"
curl -fsS "$BRIDGE_URL/healthz"
if ! curl -fsS "$N8N_HEALTH_URL"; then
  echo "[WARN] n8n health endpoint did not return 200; continuing."
fi
echo

echo "[2/4] Ingestion channel checks (dry-run)"
curl -fsS -X POST "$BRIDGE_URL/ingest/bookmarklet?dry_run=true" \
  -H "content-type: application/json" \
  -d @"$BOOKMARKLET_PAYLOAD"
echo
curl -fsS -X POST "$BRIDGE_URL/ingest/webhook?dry_run=true" \
  -H "content-type: application/json" \
  -d @"$GDOC_PAYLOAD"
echo
curl -fsS -X POST "$BRIDGE_URL/meeting/action-items?dry_run=true" \
  -H "content-type: application/json" \
  -d @"$MEETING_PAYLOAD"
echo

echo "[3/4] RAG mode checks (dry-run)"
curl -fsS -X POST "$BRIDGE_URL/query/rag?dry_run=true" \
  -H "content-type: application/json" \
  -d '{"query":"Summarize indexed content with citations.","mode":"default","top_k":5,"min_score":0.15}'
echo
curl -fsS -X POST "$BRIDGE_URL/query/rag?dry_run=true" \
  -H "content-type: application/json" \
  -d '{"query":"What should I emphasize for an Anthropic SE interview?","mode":"job-search","filter_tags":["job-search"],"top_k":5,"min_score":0.15}'
echo
curl -fsS -X POST "$BRIDGE_URL/query/rag?dry_run=true" \
  -H "content-type: application/json" \
  -d '{"query":"Summarize RAG architecture tradeoffs for enterprise use.","mode":"learning","filter_tags":["learning","genai-docs"],"top_k":5,"min_score":0.2,"max_retries":0}'
echo

echo "[4/4] Eval gate checks"
python3 "$ROOT_DIR/scripts/eval/run_eval.py" \
  --cases-file "$ROOT_DIR/scripts/eval/eval_cases.json" \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL"
python3 "$ROOT_DIR/scripts/eval/run_eval.py" \
  --cases-file "$ROOT_DIR/scripts/eval/job_search_eval_cases.json" \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL"
python3 "$ROOT_DIR/scripts/eval/run_eval.py" \
  --cases-file "$ROOT_DIR/scripts/eval/learning_eval_cases.json" \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL"

echo
echo "=== Phase 2 demo rehearsal end: $(date -u +%Y%m%dT%H%M%SZ) ==="
echo "LOG_FILE=$LOG_FILE"
