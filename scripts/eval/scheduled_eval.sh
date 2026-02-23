#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
N8N_HOST="${N8N_HOST:-http://localhost:5678}"
N8N_BASE_URL="${N8N_HOST%/}"
WEBHOOK_URL="${RECALL_EVAL_WEBHOOK_URL:-$N8N_BASE_URL/webhook/recall-query}"
ALERT_WEBHOOK_URL="${RECALL_ALERT_WEBHOOK_URL:-}"
LOG_DIR="${RECALL_EVAL_LOG_DIR:-$ROOT_DIR/data/artifacts/evals/scheduled}"
CORE_CASES_FILE="${RECALL_EVAL_CORE_CASES_FILE:-$ROOT_DIR/scripts/eval/eval_cases.json}"
JOB_SEARCH_CASES_FILE="${RECALL_EVAL_JOB_SEARCH_CASES_FILE:-$ROOT_DIR/scripts/eval/job_search_eval_cases.json}"
LEARNING_CASES_FILE="${RECALL_EVAL_LEARNING_CASES_FILE:-$ROOT_DIR/scripts/eval/learning_eval_cases.json}"
RETRY_ON_FAIL="${RECALL_EVAL_RETRY_ON_FAIL:-true}"
RETRY_DELAY_SECONDS="${RECALL_EVAL_RETRY_DELAY_SECONDS:-5}"
RETRY_ON_FAIL_NORMALIZED="$(printf '%s' "$RETRY_ON_FAIL" | tr '[:upper:]' '[:lower:]')"

mkdir -p "$LOG_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CORE_RESULT_JSON="$LOG_DIR/${STAMP}_core_eval.json"
CORE_STDERR_LOG="$LOG_DIR/${STAMP}_core_eval.stderr.log"
JOB_RESULT_JSON="$LOG_DIR/${STAMP}_job_search_eval.json"
JOB_STDERR_LOG="$LOG_DIR/${STAMP}_job_search_eval.stderr.log"
LEARNING_RESULT_JSON="$LOG_DIR/${STAMP}_learning_eval.json"
LEARNING_STDERR_LOG="$LOG_DIR/${STAMP}_learning_eval.stderr.log"

run_suite() {
  local cases_file="$1"
  local result_json="$2"
  local stderr_log="$3"

  set +e
  "$PYTHON_BIN" "$ROOT_DIR/scripts/eval/run_eval.py" \
    --cases-file "$cases_file" \
    --backend webhook \
    --webhook-url "$WEBHOOK_URL" \
    >"$result_json" 2>"$stderr_log"
  local exit_code=$?
  set -e

  if [[ "$exit_code" -ne 0 && "$RETRY_ON_FAIL_NORMALIZED" == "true" ]]; then
    sleep "$RETRY_DELAY_SECONDS"
    set +e
    "$PYTHON_BIN" "$ROOT_DIR/scripts/eval/run_eval.py" \
      --cases-file "$cases_file" \
      --backend webhook \
      --webhook-url "$WEBHOOK_URL" \
      >"$result_json" 2>"$stderr_log"
    exit_code=$?
    set -e
  fi

  return "$exit_code"
}

CORE_EXIT=0
JOB_EXIT=0
LEARNING_EXIT=0

run_suite "$CORE_CASES_FILE" "$CORE_RESULT_JSON" "$CORE_STDERR_LOG" || CORE_EXIT=$?
run_suite "$JOB_SEARCH_CASES_FILE" "$JOB_RESULT_JSON" "$JOB_STDERR_LOG" || JOB_EXIT=$?
run_suite "$LEARNING_CASES_FILE" "$LEARNING_RESULT_JSON" "$LEARNING_STDERR_LOG" || LEARNING_EXIT=$?

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
