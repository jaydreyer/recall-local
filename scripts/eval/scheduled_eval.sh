#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
WEBHOOK_URL="${RECALL_EVAL_WEBHOOK_URL:-http://100.116.103.78:5678/webhook/recall-query}"
ALERT_WEBHOOK_URL="${RECALL_ALERT_WEBHOOK_URL:-}"
LOG_DIR="${RECALL_EVAL_LOG_DIR:-$ROOT_DIR/data/artifacts/evals/scheduled}"
CORE_CASES_FILE="${RECALL_EVAL_CORE_CASES_FILE:-$ROOT_DIR/scripts/eval/eval_cases.json}"
JOB_SEARCH_CASES_FILE="${RECALL_EVAL_JOB_SEARCH_CASES_FILE:-$ROOT_DIR/scripts/eval/job_search_eval_cases.json}"
LEARNING_CASES_FILE="${RECALL_EVAL_LEARNING_CASES_FILE:-$ROOT_DIR/scripts/eval/learning_eval_cases.json}"

mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CORE_RESULT_JSON="$LOG_DIR/${STAMP}_core_eval.json"
CORE_STDERR_LOG="$LOG_DIR/${STAMP}_core_eval.stderr.log"
JOB_RESULT_JSON="$LOG_DIR/${STAMP}_job_search_eval.json"
JOB_STDERR_LOG="$LOG_DIR/${STAMP}_job_search_eval.stderr.log"
LEARNING_RESULT_JSON="$LOG_DIR/${STAMP}_learning_eval.json"
LEARNING_STDERR_LOG="$LOG_DIR/${STAMP}_learning_eval.stderr.log"

set +e
"$PYTHON_BIN" "$ROOT_DIR/scripts/eval/run_eval.py" \
  --cases-file "$CORE_CASES_FILE" \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL" \
  >"$CORE_RESULT_JSON" 2>"$CORE_STDERR_LOG"
CORE_EXIT=$?

"$PYTHON_BIN" "$ROOT_DIR/scripts/eval/run_eval.py" \
  --cases-file "$JOB_SEARCH_CASES_FILE" \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL" \
  >"$JOB_RESULT_JSON" 2>"$JOB_STDERR_LOG"
JOB_EXIT=$?

"$PYTHON_BIN" "$ROOT_DIR/scripts/eval/run_eval.py" \
  --cases-file "$LEARNING_CASES_FILE" \
  --backend webhook \
  --webhook-url "$WEBHOOK_URL" \
  >"$LEARNING_RESULT_JSON" 2>"$LEARNING_STDERR_LOG"
LEARNING_EXIT=$?
set -e

"$PYTHON_BIN" "$ROOT_DIR/scripts/eval/notify_regression.py" \
  --result-json "$CORE_RESULT_JSON" \
  --command-exit "$CORE_EXIT" \
  --webhook-url "$ALERT_WEBHOOK_URL" \
  --stderr-log "$CORE_STDERR_LOG"

"$PYTHON_BIN" "$ROOT_DIR/scripts/eval/notify_regression.py" \
  --result-json "$JOB_RESULT_JSON" \
  --command-exit "$JOB_EXIT" \
  --webhook-url "$ALERT_WEBHOOK_URL" \
  --stderr-log "$JOB_STDERR_LOG"

"$PYTHON_BIN" "$ROOT_DIR/scripts/eval/notify_regression.py" \
  --result-json "$LEARNING_RESULT_JSON" \
  --command-exit "$LEARNING_EXIT" \
  --webhook-url "$ALERT_WEBHOOK_URL" \
  --stderr-log "$LEARNING_STDERR_LOG"

if [[ "$CORE_EXIT" -ne 0 || "$JOB_EXIT" -ne 0 || "$LEARNING_EXIT" -ne 0 ]]; then
  if [[ "$CORE_EXIT" -ne 0 ]]; then
    exit "$CORE_EXIT"
  fi
  if [[ "$JOB_EXIT" -ne 0 ]]; then
    exit "$JOB_EXIT"
  fi
  exit "$LEARNING_EXIT"
fi

echo "Scheduled eval completed successfully:"
echo "  core: $CORE_RESULT_JSON"
echo "  job-search: $JOB_RESULT_JSON"
echo "  learning: $LEARNING_RESULT_JSON"
