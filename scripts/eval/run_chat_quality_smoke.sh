#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CASES_FILE="$ROOT_DIR/scripts/eval/chat_quality_smoke_cases.json"
EVAL_SCRIPT="$ROOT_DIR/scripts/eval/run_eval.py"

WEBHOOK_URL="${1:-http://localhost:8090/v1/rag-queries}"

python3 "$EVAL_SCRIPT" \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL" \
  --cases-file "$CASES_FILE" \
  --top-k 8 \
  --max-retries 2 \
  --retrieval-mode hybrid \
  --enable-reranker true \
  --reranker-weight 0.65
