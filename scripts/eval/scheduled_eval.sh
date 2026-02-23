#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
WEBHOOK_URL="${RECALL_EVAL_WEBHOOK_URL:-http://100.116.103.78:5678/webhook/recall-query}"
ALERT_WEBHOOK_URL="${RECALL_ALERT_WEBHOOK_URL:-}"
LOG_DIR="${RECALL_EVAL_LOG_DIR:-$ROOT_DIR/data/artifacts/evals/scheduled}"

mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RESULT_JSON="$LOG_DIR/${STAMP}_eval.json"
STDERR_LOG="$LOG_DIR/${STAMP}_eval.stderr.log"

set +e
"$PYTHON_BIN" "$ROOT_DIR/scripts/eval/run_eval.py" \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL" \
  >"$RESULT_JSON" 2>"$STDERR_LOG"
EVAL_EXIT=$?
set -e

"$PYTHON_BIN" "$ROOT_DIR/scripts/eval/notify_regression.py" \
  --result-json "$RESULT_JSON" \
  --command-exit "$EVAL_EXIT" \
  --webhook-url "$ALERT_WEBHOOK_URL" \
  --stderr-log "$STDERR_LOG"

if [[ "$EVAL_EXIT" -ne 0 ]]; then
  exit "$EVAL_EXIT"
fi

echo "Scheduled eval completed successfully: $RESULT_JSON"
