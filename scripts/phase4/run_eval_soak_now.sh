#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

ITERATIONS=5
DELAY_SECONDS=0
SUITE="both"
OUTPUT_DIR_OVERRIDE=""
N8N_HOST_OVERRIDE=""
WEBHOOK_URL_OVERRIDE=""
CORE_CASES_FILE="${RECALL_EVAL_CORE_CASES_FILE:-$ROOT_DIR/scripts/eval/eval_cases.json}"
JOB_SEARCH_CASES_FILE="${RECALL_EVAL_JOB_SEARCH_CASES_FILE:-$ROOT_DIR/scripts/eval/job_search_eval_cases.json}"
MIN_PASS_RATE="${RECALL_PHASE4_MIN_PASS_RATE:-1.0}"
MAX_AVG_LATENCY_MS="${RECALL_PHASE4_MAX_AVG_LATENCY_MS:-15000}"
FAIL_ON_THRESHOLD="true"

usage() {
  cat <<'EOF'
Usage:
  run_eval_soak_now.sh [options]

Options:
  --iterations <n>             Number of sequential runs per suite (default: 5)
  --delay-seconds <n>          Delay between runs in seconds (default: 0)
  --suite <core|job-search|both>
                               Suite selector (default: both)
  --output-dir <path>          Output directory for run artifacts
  --n8n-host <url>             Override N8N host (example: http://localhost:5678)
  --webhook-url <url>          Override eval webhook URL directly
  --core-cases-file <path>     Override core eval cases file
  --job-cases-file <path>      Override job-search eval cases file
  --min-pass-rate <0..1>       Minimum average per-run case pass-rate threshold
  --max-avg-latency-ms <n>     Maximum average run latency threshold in milliseconds
  --no-fail-on-threshold       Always exit 0 after summary generation
  --help                       Show this help

Examples:
  run_eval_soak_now.sh
  run_eval_soak_now.sh --iterations 7 --delay-seconds 10 --suite both
  run_eval_soak_now.sh --n8n-host http://100.116.103.78:5678 --iterations 5
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iterations)
      ITERATIONS="${2:-}"
      shift 2
      ;;
    --delay-seconds)
      DELAY_SECONDS="${2:-}"
      shift 2
      ;;
    --suite)
      SUITE="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR_OVERRIDE="${2:-}"
      shift 2
      ;;
    --n8n-host)
      N8N_HOST_OVERRIDE="${2:-}"
      shift 2
      ;;
    --webhook-url)
      WEBHOOK_URL_OVERRIDE="${2:-}"
      shift 2
      ;;
    --core-cases-file)
      CORE_CASES_FILE="${2:-}"
      shift 2
      ;;
    --job-cases-file)
      JOB_SEARCH_CASES_FILE="${2:-}"
      shift 2
      ;;
    --min-pass-rate)
      MIN_PASS_RATE="${2:-}"
      shift 2
      ;;
    --max-avg-latency-ms)
      MAX_AVG_LATENCY_MS="${2:-}"
      shift 2
      ;;
    --no-fail-on-threshold)
      FAIL_ON_THRESHOLD="false"
      shift 1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$ITERATIONS" =~ ^[0-9]+$ ]] || [[ "$ITERATIONS" -le 0 ]]; then
  echo "--iterations must be a positive integer." >&2
  exit 2
fi

if ! [[ "$DELAY_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "--delay-seconds must be a non-negative integer." >&2
  exit 2
fi

if ! [[ "$MAX_AVG_LATENCY_MS" =~ ^[0-9]+$ ]]; then
  echo "--max-avg-latency-ms must be a non-negative integer." >&2
  exit 2
fi

case "$SUITE" in
  core|job-search|both)
    ;;
  *)
    echo "--suite must be one of: core, job-search, both." >&2
    exit 2
    ;;
esac

if [[ -n "$N8N_HOST_OVERRIDE" ]]; then
  export N8N_HOST="$N8N_HOST_OVERRIDE"
fi
if [[ -n "$WEBHOOK_URL_OVERRIDE" ]]; then
  export RECALL_EVAL_WEBHOOK_URL="$WEBHOOK_URL_OVERRIDE"
fi

N8N_HOST="${N8N_HOST:-http://localhost:5678}"
N8N_BASE_URL="${N8N_HOST%/}"
WEBHOOK_URL="${RECALL_EVAL_WEBHOOK_URL:-$N8N_BASE_URL/webhook/recall-query}"

SOAK_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SOAK_DIR="${OUTPUT_DIR_OVERRIDE:-$ROOT_DIR/data/artifacts/evals/phase4_soak/$SOAK_STAMP}"
mkdir -p "$SOAK_DIR"

declare -a SUITES
if [[ "$SUITE" == "both" ]]; then
  SUITES=("core" "job-search")
else
  SUITES=("$SUITE")
fi

for suite_name in "${SUITES[@]}"; do
  case "$suite_name" in
    core)
      cases_file="$CORE_CASES_FILE"
      ;;
    job-search)
      cases_file="$JOB_SEARCH_CASES_FILE"
      ;;
    *)
      echo "Unexpected suite: $suite_name" >&2
      exit 2
      ;;
  esac

  if [[ ! -f "$cases_file" ]]; then
    echo "Cases file not found for suite '$suite_name': $cases_file" >&2
    exit 2
  fi

  for ((iteration = 1; iteration <= ITERATIONS; iteration++)); do
    run_label="$(printf '%s_run%02d' "$suite_name" "$iteration")"
    result_json="$SOAK_DIR/${run_label}.json"
    stderr_log="$SOAK_DIR/${run_label}.stderr.log"
    meta_json="$SOAK_DIR/${run_label}.meta.json"

    echo "Running suite=$suite_name iteration=$iteration/$ITERATIONS"
    set +e
    "$PYTHON_BIN" "$ROOT_DIR/scripts/eval/run_eval.py" \
      --cases-file "$cases_file" \
      --backend webhook \
      --webhook-url "$WEBHOOK_URL" \
      >"$result_json" 2>"$stderr_log"
    command_exit=$?
    set -e

    cat >"$meta_json" <<EOF
{
  "suite": "$suite_name",
  "iteration": $iteration,
  "command_exit": $command_exit,
  "result_json": "$result_json",
  "stderr_log": "$stderr_log",
  "cases_file": "$cases_file",
  "webhook_url": "$WEBHOOK_URL"
}
EOF

    if [[ "$iteration" -lt "$ITERATIONS" && "$DELAY_SECONDS" -gt 0 ]]; then
      sleep "$DELAY_SECONDS"
    fi
  done
done

SUMMARY_JSON="$SOAK_DIR/soak_summary.json"
SUMMARY_MARKDOWN="$SOAK_DIR/soak_summary.md"
SUMMARY_LABEL="Phase 4A eval soak ($SOAK_STAMP)"

SUMMARY_CMD=(
  "$PYTHON_BIN"
  "$ROOT_DIR/scripts/phase4/summarize_eval_trend.py"
  --meta-glob
  "$SOAK_DIR/*.meta.json"
  --output-json
  "$SUMMARY_JSON"
  --output-markdown
  "$SUMMARY_MARKDOWN"
  --min-pass-rate
  "$MIN_PASS_RATE"
  --max-avg-latency-ms
  "$MAX_AVG_LATENCY_MS"
  --label
  "$SUMMARY_LABEL"
)

if [[ "$FAIL_ON_THRESHOLD" == "true" ]]; then
  SUMMARY_CMD+=(--fail-on-threshold)
fi

set +e
"${SUMMARY_CMD[@]}"
SUMMARY_EXIT=$?
set -e

echo "Phase 4 soak artifacts:"
echo "  run dir: $SOAK_DIR"
echo "  summary json: $SUMMARY_JSON"
echo "  summary markdown: $SUMMARY_MARKDOWN"

exit "$SUMMARY_EXIT"
